import asyncio
import discord
from discord import Member
from config import (
    MIN_PLAYERS, AUTO_MODE_TIMEOUT, HOSTED_MODE_TIMEOUT,
    POINTS, ROLE_EMOJIS, ROLE_DESCRIPTIONS, ROLE_REGISTRY,
    ADMIN_USER_ID, PRESHOUT_CHANNEL_ID, NOMINATIONS_REQUIRED,
)
from bot.game.player import Player
from bot.game.role import assign_roles, get_role_team, is_killing_role, get_points_key
from bot.game.channels import setup_game_channels, add_mafia_permissions, cleanup_game_channels
from bot.game.night_actions import collect_night_actions, resolve_night_actions
from bot.game.day_actions import run_nomination_phase, run_trial_phase
from bot.database.db import add_points, increment_games_played, increment_games_won, log_game


class GameManager:
    _instance = None

    def __init__(self):
        self.games = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create_game(self, guild_id, channel_id, is_auto=False, is_hosted=False, game_type="Mafia"):
        game = GameInstance(guild_id, channel_id, is_auto, is_hosted, game_type)
        self.games[guild_id] = game
        return game

    def get_game(self, guild_id):
        return self.games.get(guild_id)

    def remove_game(self, guild_id):
        if guild_id in self.games:
            del self.games[guild_id]


class GameInstance:
    def __init__(self, guild_id, channel_id, is_auto=False, is_hosted=False, game_type="Mafia"):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.is_auto = is_auto
        self.is_hosted = is_hosted
        self.game_type = game_type
        self.state = "lobby"
        self.players = []
        self.day_number = 0
        self.night_number = 0
        self.game_category = None
        self.town_square = None
        self.mafia_den = None
        self.dead_chat = None
        self.player_role = None
        self.dead_role = None
        self.night_actions_queue = {}
        self.nomination_counts = {}
        self.trial_player = None
        self.votes = {}
        self.night_log = []
        self._tasks = []
        self.mafia_team = []
        self.preshout_message = None
        self.join_button_active = False
        self._force_advance = False
        self._force_day = False
        self.point_bonus = False
        self._game_id = id(self)

    @property
    def alive_players(self):
        return [p for p in self.players if p.alive]

    @property
    def dead_players(self):
        return [p for p in self.players if not p.alive]

    @property
    def living_mafia(self):
        return [p for p in self.alive_players if get_role_team(p.role) == "mafia"]

    @property
    def living_town(self):
        return [p for p in self.alive_players if get_role_team(p.role) == "town"]

    @property
    def living_neutral(self):
        return [p for p in self.alive_players if get_role_team(p.role) == "neutral"]

    def get_player_by_id(self, user_id):
        for p in self.players:
            if p.user_id == user_id:
                return p
        return None

    def add_player(self, user: Member):
        if self.state != "lobby":
            return None
        if any(p.user_id == user.id for p in self.players):
            return None
        player = Player(user)
        self.players.append(player)
        return player

    async def start_game(self, bot):
        self.state = "playing"
        guild = bot.get_guild(self.guild_id)
        if not guild:
            return

        await setup_game_channels(self, guild)

        for p in self.players:
            member = guild.get_member(p.user_id)
            if member:
                p.original_roles = [r.id for r in member.roles if r.name != "@everyone" and not r.managed]
                await member.edit(roles=[self.player_role])
                await member.add_roles(self.player_role)

        assignments, self.mafia_team = assign_roles(len(self.players), self.players)

        await add_mafia_permissions(self, guild, self.mafia_team)

        await self._send_role_dms(bot)

        mafia_count = len(self.living_mafia)
        neutral_count = len(self.living_neutral)
        town_count = len(self.living_town)
        announce = f"**Teams:** 🔪 {mafia_count} Mafia | 🎭 {neutral_count} Neutral | 🏘️ {town_count} Town"
        await self.town_square.send(announce)

        await self._run_game_loop(bot)

    async def _send_role_dms(self, bot):
        mafia_ids = [p.user_id for p in self.mafia_team]
        mafia_names = ", ".join(p.mention for p in self.mafia_team)

        for p in self.players:
            emoji = ROLE_EMOJIS.get(p.role, "❓")
            desc = ROLE_DESCRIPTIONS.get(p.role, "No special ability.")
            team = get_role_team(p.role)
            embed = discord.Embed(
                title=f"{emoji} Your Role: {p.role.replace('_', ' ').title()}",
                description=f"**Team:** {team.title()}\n**Ability:** {desc}",
                color=discord.Color.dark_blue()
            )
            if team == "mafia":
                embed.add_field(name="👥 Teammates", value=mafia_names, inline=False)
            if p.role == "bounty_hunter":
                target_role = self._get_bh_target_role(p)
                p.bh_target_role = target_role
                embed.add_field(name="🎯 Target", value=f"Your target is the **{target_role}**", inline=False)
            try:
                await p.member.send(embed=embed)
            except discord.Forbidden:
                pass

    def _get_bh_target_role(self, player):
        import random
        targets = [p for p in self.players if p.user_id != player.user_id]
        if not targets:
            return "Town"
        target = random.choice(targets)
        return target.role

    async def _run_game_loop(self, bot):
        try:
            while True:
                await self._night_phase(bot)
                check = self._check_win_condition()
                if check:
                    await self.end_game(bot, check)
                    return

                await self._day_phase(bot)
                check = self._check_win_condition()
                if check:
                    await self.end_game(bot, check)
                    return
        except Exception as e:
            print(f"Game error: {e}")
            await self.end_game(bot, "error")

    async def _night_phase(self, bot):
        self._force_advance = False
        guild = bot.get_guild(self.guild_id)
        self.night_number += 1

        await self._toggle_mafia_chat(guild, open_chat=True)

        msg = f"🌙 **Night {self.night_number} falls.** The town sleeps..."
        if any(p.role not in ("town",) and p.alive for p in self.players):
            msg += "\n(Special roles: check your DMs)"
        await self.town_square.send(msg)

        await collect_night_actions(self, bot)

        if self._force_advance:
            self._force_advance = False

        deaths, janitor_target = await resolve_night_actions(self)
        deaths = [d for d in deaths if d[0].alive]

        await self._toggle_mafia_chat(guild, open_chat=False)

        await self._announce_morning(deaths, janitor_target, guild, bot)

        for victim, cause in deaths:
            if victim.alive:
                await self._kill_player(guild, victim)

        self._check_neutral_wins(bot, guild)

        if self._check_mafia_promotion():
            await self._promote_mafia(bot, guild)

    async def _toggle_mafia_chat(self, guild, open_chat):
        if not self.mafia_den:
            return
        for player in self.players:
            if get_role_team(player.role) == "mafia" and player.alive:
                member = guild.get_member(player.user_id)
                if member:
                    if open_chat:
                        await self.mafia_den.set_permissions(member, read_messages=True, send_messages=True)
                    else:
                        await self.mafia_den.set_permissions(member, overwrite=None)

    async def _announce_morning(self, deaths, janitor_target, guild, bot):
        self.day_number += 1
        msg = f"🌅 **Morning comes...**\n"

        if deaths:
            for victim, cause in deaths:
                if cause == "mafia_kill" and janitor_target == victim.user_id:
                    msg += f"💀 Somebody was killed last night, but the body was never found.\n"
                elif cause == "mafia_kill":
                    msg += f"💀 {victim.mention} was found dead. The Mafia struck in the night.\n"
                    msg += f"🏘️ They were **{victim.role.replace('_', ' ').title()}**.\n"
                elif cause == "duel":
                    msg += f"🏴‍☠️ {victim.mention} was killed in a duel!\n"
                elif cause == "veteran":
                    msg += f"🎖️ {victim.mention} visited a Veteran on alert and was killed!\n"
        else:
            msg += "☀️ Nobody died last night.\n"

        msg += f"\n☀️ **Day {self.day_number}** — {len(self.alive_players)} players alive."
        await self.town_square.send(msg)

    async def _kill_player(self, guild, player):
        player.alive = False
        member = guild.get_member(player.user_id)
        if member:
            try:
                await member.remove_roles(self.player_role)
                await member.add_roles(self.dead_role)
                await self.town_square.set_permissions(member, overwrite=None)
                await self.dead_chat.set_permissions(member, read_messages=True, send_messages=True)
            except:
                pass

        entry = {
            "type": "death",
            "target_id": player.user_id,
            "role": player.role,
            "alive": False
        }
        self.night_log.append(entry)

    async def _day_phase(self, bot):
        self._force_advance = False
        self._force_day = False

        msg = f"☀️ **Day {self.day_number}** — Nominate someone for trial via your DMs! ({NOMINATIONS_REQUIRED}+ nomination(s) required.)"
        await self.town_square.send(msg)

        accused = await run_nomination_phase(self, bot)

        if self._force_advance:
            self._force_advance = False

        if accused:
            victim = await run_trial_phase(self, bot, accused)
            if victim:
                guild = bot.get_guild(self.guild_id)
                await self._kill_player(guild, victim)
                jester_check = any(p for p in self.players if p.role == "jester" and not p.alive and p.user_id == victim.user_id)
                if jester_check:
                    await self.town_square.send(f"🤡 {victim.mention} was the **Jester** and wins!")
                    self._award_points_for_player(victim, "jester_win")
                else:
                    await self.town_square.send(f"⚖️ {victim.mention} was found guilty and eliminated!")
                self._check_neutral_wins(bot, bot.get_guild(self.guild_id))
        else:
            await self.town_square.send(f"📭 No trial today. Nobody reached the required {NOMINATIONS_REQUIRED} nomination(s).")

    def _check_win_condition(self):
        alive_mafia = len(self.living_mafia)
        alive_others = len(self.alive_players) - alive_mafia

        if alive_mafia == 0:
            return "town"
        if alive_mafia >= alive_others:
            return "mafia"
        return None

    def _check_neutral_wins(self, bot, guild):
        for player in self.players:
            if not player.alive:
                continue
            if player.role == "pirate" and player.duel_wins >= 2:
                self._award_points_for_player(player, "neutral_win")
                player.alive = False
                asyncio.ensure_future(self._kill_player(guild, player))
                asyncio.ensure_future(self.town_square.send(f"🏴‍☠️ {player.mention} the **Pirate** won their duels and sails away!"))
            if player.role == "teleporter" and self._check_win_condition() is not None:
                self._award_points_for_player(player, "neutral_win")
            if player.role == "veteran":
                pass
            if player.role == "bounty_hunter" and player.bh_killed and player.alive:
                self._award_points_for_player(player, "bh_win")

    def _check_mafia_promotion(self):
        killing_mafia = [p for p in self.living_mafia if is_killing_role(p.role)]
        if len(killing_mafia) == 0 and len(self.living_mafia) > 0:
            return True
        return False

    async def _promote_mafia(self, bot, guild):
        import random
        candidates = [p for p in self.living_mafia if not is_killing_role(p.role)]
        if not candidates:
            return
        promoted = random.choice(candidates)
        promoted.role = "mafia"
        try:
            await promoted.member.send("🔪 You have been promoted to **Mafia Killer**! You can now kill at night.")
        except:
            pass
        mafia_names = ", ".join(p.mention for p in self.living_mafia)
        for p in self.living_mafia:
            try:
                await p.member.send(f"🔄 {promoted.mention} is now the **Mafia Killer**.")
            except:
                pass

    def _award_points_for_player(self, player, points_key):
        is_bonus = self.is_hosted
        key = points_key
        if is_bonus:
            bonus_key = f"{points_key}_bonus"
            if bonus_key in POINTS:
                key = bonus_key
        points = POINTS.get(key, 0)
        player.points_earned = points
        add_points(player.user_id, points)
        increment_games_won(player.user_id)

    async def end_game(self, bot, reason):
        guild = bot.get_guild(self.guild_id)
        channel = bot.get_channel(self.channel_id)

        if reason == "town":
            winner_msg = "🏘️ **Town wins!** All Mafia have been eliminated."
        elif reason == "mafia":
            winner_msg = "🔪 **Mafia wins!** They now control the town."
        elif reason == "error":
            winner_msg = "⚠️ Game ended due to an internal error."
        elif reason == "admin_ended":
            winner_msg = "⚠️ Game ended by admin."
        else:
            winner_msg = "⚠️ Game over."

        points_log = []

        for p in self.players:
            increment_games_played(p.user_id)

        if reason in ("town", "mafia"):
            for p in self.alive_players:
                team = get_role_team(p.role)
                if reason == "town" and team == "town":
                    self._award_points_for_player(p, "town_win")
                elif reason == "mafia" and team == "mafia":
                    self._award_points_for_player(p, "mafia_win")
                elif team == "neutral" and p.alive and p.role in ("veteran", "teleporter"):
                    self._award_points_for_player(p, "neutral_win")

            for p in self.players:
                if p.points_earned == 0:
                    add_points(p.user_id, POINTS["participation"])
                    points_log.append(f"{p.mention}: +{POINTS['participation']} (participation)")
                else:
                    points_log.append(f"{p.mention}: +{p.points_earned} (winner)")

        elif reason in ("error", "admin_ended"):
            for p in self.players:
                add_points(p.user_id, POINTS["premature_end"])
                points_log.append(f"{p.mention}: +{POINTS['premature_end']} (early end)")

        summary = f"{winner_msg}"
        if points_log:
            summary += f"\n\n**Points awarded:**\n" + "\n".join(points_log)

        role_list = "\n".join(
            f"{'💀' if not p.alive else '✅'} {p.mention} — {ROLE_EMOJIS.get(p.role, '❓')} {p.role.replace('_', ' ').title()}"
            for p in self.players
        )

        night_summary = ""
        for i, entry in enumerate(self.night_log, 1):
            death_type = entry.get("type", "")
            if death_type in ("death", "mafia_kill"):
                p = self.get_player_by_id(entry.get("target_id"))
                if p:
                    cleaned = " (body cleaned)" if entry.get("cleaned") else ""
                    night_summary += f"N{i}: {p.mention} died{cleaned}\n"

        full_summary = f"{summary}\n\n**Roles:**\n{role_list}"
        if night_summary:
            full_summary += f"\n\n**Night Log:**\n{night_summary}"

        if channel:
            await channel.send(full_summary[:2000])

        await cleanup_game_channels(self, guild)
        GameManager.get_instance().remove_game(self.guild_id)

        if reason in ("town", "mafia"):
            log_game(self.game_type, len(self.players), reason, {
                "winner_team": reason,
                "player_count": len(self.players),
                "day_number": self.day_number,
            })
