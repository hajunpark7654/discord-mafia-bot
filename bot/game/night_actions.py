import asyncio
import random
import discord
from config import ROLE_EMOJIS, ROLE_DESCRIPTIONS, ROLE_REGISTRY
from bot.game.role import is_killing_role


def get_role_team(role_name):
    info = ROLE_REGISTRY.get(role_name, {})
    return info.get("team", "town")


async def collect_night_actions(game, bot):
    game.night_actions_queue = {}
    for player in game.alive_players:
        game.night_actions_queue[player.user_id] = {"action": None, "target": None}

    coros = []
    for player in game.alive_players:
        coro = send_night_dm(player, game, bot)
        coros.append(coro)
    await asyncio.gather(*coros)

    if getattr(game, 'test_mode', False):
        for player in game.alive_players:
            if not player.is_dummy:
                continue
            if is_killing_role(player.role):
                targets = [p for p in game.alive_players if not p.is_dummy and get_role_team(p.role) != "mafia"]
                if targets:
                    target = random.choice(targets)
                    game.night_actions_queue[player.user_id] = {"action": "kill", "target": target.user_id}
                else:
                    targets = [p for p in game.alive_players if get_role_team(p.role) != "mafia"]
                    if targets:
                        target = random.choice(targets)
                        game.night_actions_queue[player.user_id] = {"action": "kill", "target": target.user_id}
            else:
                if game.night_actions_queue[player.user_id]["action"] is None:
                    game.night_actions_queue[player.user_id] = {"action": "skip", "target": None}

    timeout = 10 if getattr(game, 'test_mode', False) else (300 if game.is_auto else 600)
    check_interval = 5
    elapsed = 0
    while elapsed < timeout:
        await asyncio.sleep(min(check_interval, timeout - elapsed))
        elapsed += check_interval
        if getattr(game, '_force_advance', False):
            setattr(game, '_force_advance', False)
            break
        if getattr(game, '_cancel_token', None) and game._cancel_token.is_set():
            break

    for uid, data in game.night_actions_queue.items():
        if data["action"] is None:
            data["action"] = "skip"


async def send_night_dm(player, game, bot):
    if player.is_dummy or not player.member:
        return
    role_name = player.role
    if role_name == "town":
        return
    sender_map = {
        "mafia": send_mafia_kill_dm,
        "doctor": send_doctor_dm,
        "sheriff": send_sheriff_dm,
        "framer": send_framer_dm,
        "consort": send_consort_dm,
        "janitor": send_janitor_dm,
        "psychic": send_psychic_dm,
        "lookout": send_lookout_dm,
        "pirate": send_pirate_dm,
        "teleporter": send_teleporter_dm,
        "veteran": send_veteran_dm,
        "bounty_hunter": send_bounty_hunter_dm,
    }
    sender = sender_map.get(role_name)
    if sender:
        await sender(player, game, bot)


async def build_target_select(player, game, prompt, targets, action_key):
    if not targets:
        return None, None
    embed = discord.Embed(title=prompt, color=discord.Color.dark_red())
    options = []
    for p in targets[:25]:
        label = p.name[:100]
        options.append(discord.SelectOption(label=label, value=str(p.user_id)))
    view = discord.ui.View()
    select = discord.ui.Select(placeholder="Choose a player...", options=options)

    async def select_callback(interaction):
        if interaction.user.id != player.user_id:
            return
        target_id = int(select.values[0])
        game.night_actions_queue[player.user_id] = {"action": action_key, "target": target_id}
        await interaction.response.send_message(f"✅ Action recorded: {action_key}", ephemeral=True)

    select.callback = select_callback
    view.add_item(select)
    return embed, view


async def send_simple_dm(player, text):
    if not player.member:
        return
    try:
        await player.member.send(text)
    except discord.Forbidden:
        pass


async def send_mafia_kill_dm(player, game, bot):
    targets = [p for p in game.alive_players if get_role_team(p.role) != "mafia"]
    embed, view = await build_target_select(player, game, "🔪 Choose someone to kill tonight:", targets, "kill")
    if embed:
        await send_dm(player, embed, view)


async def send_doctor_dm(player, game, bot):
    embed, view = await build_target_select(player, game, "💉 Choose someone to protect tonight:", game.alive_players, "protect")
    if embed:
        await send_dm(player, embed, view)


async def send_sheriff_dm(player, game, bot):
    targets = [p for p in game.alive_players if p.user_id != player.user_id]
    embed, view = await build_target_select(player, game, "🔎 Choose someone to investigate:", targets, "investigate")
    if embed:
        await send_dm(player, embed, view)


async def send_framer_dm(player, game, bot):
    targets = [p for p in game.alive_players if p.user_id != player.user_id]
    embed, view = await build_target_select(player, game, "🖼️ Choose someone to frame:", targets, "frame")
    if embed:
        await send_dm(player, embed, view)


async def send_consort_dm(player, game, bot):
    targets = [p for p in game.alive_players if get_role_team(p.role) != "mafia" and p.user_id != player.user_id]
    embed, view = await build_target_select(player, game, "🔒 Choose someone to roleblock:", targets, "roleblock")
    if embed:
        await send_dm(player, embed, view)


async def send_janitor_dm(player, game, bot):
    if player.janitor_used:
        return
    last_night_kill = None
    prev_nights = [n for n in sorted(game.night_log.keys()) if n < game.night_number]
    if prev_nights:
        last_night = prev_nights[-1]
        for entry in reversed(game.night_log[last_night]):
            if entry.get("type") == "mafia_kill":
                last_night_kill = entry
                break
    if last_night_kill:
        target_id = last_night_kill.get("target_id")
        target = game.get_player_by_id(target_id)
        if target:
            embed, view = await build_target_select(player, game, "🧹 Clean the body (one-time use):", [target], "janitor")
            if embed:
                await send_dm(player, embed, view)


async def send_lookout_dm(player, game, bot):
    targets = [p for p in game.alive_players if p.user_id != player.user_id]
    embed, view = await build_target_select(player, game, "👁️ Choose someone to watch:", targets, "watch")
    if embed:
        await send_dm(player, embed, view)


async def send_pirate_dm(player, game, bot):
    targets = [p for p in game.alive_players if p.user_id != player.user_id]
    embed, view = await build_target_select(player, game, "🏴‍☠️ Choose someone to duel:", targets, "duel")
    if embed:
        await send_dm(player, embed, view)


async def send_teleporter_dm(player, game, bot):
    targets = game.alive_players
    embed, view = await build_target_select(player, game, "🌀 Choose first player to swap:", targets, "swap1")
    if embed:
        await send_dm(player, embed, view)


async def send_veteran_dm(player, game, bot):
    if player.alerts_used >= 2:
        return
    view = discord.ui.View()
    yes_btn = discord.ui.Button(label="Yes - Go on Alert", style=discord.ButtonStyle.danger)
    no_btn = discord.ui.Button(label="No - Stay Passive", style=discord.ButtonStyle.secondary)

    async def yes_callback(interaction):
        if interaction.user.id != player.user_id:
            return
        game.night_actions_queue[player.user_id] = {"action": "alert", "target": None, "alert": True}
        await interaction.response.send_message("🎖️ You are on alert tonight! Visitors will be killed.", ephemeral=True)

    async def no_callback(interaction):
        if interaction.user.id != player.user_id:
            return
        game.night_actions_queue[player.user_id] = {"action": "skip", "target": None}
        await interaction.response.send_message("You stay passive.", ephemeral=True)

    yes_btn.callback = yes_callback
    no_btn.callback = no_callback
    view.add_item(yes_btn)
    view.add_item(no_btn)
    embed = discord.Embed(
        title="🎖️ Veteran Alert",
        description=f"Do you want to use an alert tonight? ({2 - player.alerts_used} remaining)",
        color=discord.Color.dark_gold()
    )
    await send_dm(player, embed, view)


async def send_psychic_dm(player, game, bot):
    if game.night_number % 2 == 0:
        pool = [p for p in game.alive_players if p.user_id != player.user_id]
        if len(pool) >= 3:
            chosen = random.sample(pool, 3)
            names = ", ".join(p.mention for p in chosen)
            await send_simple_dm(player, f"🔮 **Psychic Vision:** At least one of these players is evil: {names}")
            game.night_actions_queue[player.user_id] = {"action": "psychic", "target": None}


async def send_bounty_hunter_dm(player, game, bot):
    if player.bh_killed:
        return
    targets = [p for p in game.alive_players if p.user_id != player.user_id]
    embed, view = await build_target_select(player, game, "🎯 Choose your target to eliminate:", targets, "bh_kill")
    if embed:
        await send_dm(player, embed, view)


async def send_dm(player, embed, view):
    if not player.member:
        return
    try:
        await player.member.send(embed=embed, view=view)
    except discord.Forbidden:
        pass


def resolve_rps(p1, p2):
    choices = ["rock", "paper", "scissors"]
    c1 = random.choice(choices)
    c2 = random.choice(choices)
    if c1 == c2:
        return resolve_rps(p1, p2)
    if (c1 == "rock" and c2 == "scissors") or \
       (c1 == "paper" and c2 == "rock") or \
       (c1 == "scissors" and c2 == "paper"):
        return p1
    return p2


async def resolve_night_actions(game):
    deaths = []
    entries = []
    protections = set()
    roleblocks = set()
    frames = set()
    veteran_alerts = set()
    janitor_target = None

    for uid, data in game.night_actions_queue.items():
        player = game.get_player_by_id(uid)
        if not player or not player.alive:
            continue
        action = data.get("action")
        if action == "roleblock":
            roleblocks.add(data.get("target"))
        if action == "alert":
            veteran_alerts.add(player.user_id)

    for uid in veteran_alerts:
        player = game.get_player_by_id(uid)
        if player:
            player.alerts_used += 1
            visitors = []
            for other_uid, other_data in game.night_actions_queue.items():
                if other_data.get("target") == uid and other_uid != uid:
                    other_player = game.get_player_by_id(other_uid)
                    if other_player and other_player.alive:
                        visitors.append(other_player)
            for v in visitors:
                deaths.append((v, "veteran"))
                entries.append({"type": "veteran_kill", "target_id": v.user_id})

    for uid, data in game.night_actions_queue.items():
        player = game.get_player_by_id(uid)
        if not player or not player.alive:
            continue
        action = data.get("action")
        target_id = data.get("target")

        if uid in roleblocks:
            if action in ("kill", "protect", "investigate", "watch", "duel", "swap1", "frame", "bh_kill"):
                entries.append({"type": "roleblock", "target_id": uid})
                continue
            continue

        if action == "protect":
            if uid == target_id:
                if player.self_heal_used:
                    continue
                player.self_heal_used = True
            protections.add(target_id)
        elif action == "investigate":
            target = game.get_player_by_id(target_id)
            if target:
                is_suspicious = get_role_team(target.role) in ("mafia", "neutral")
                is_framed = target_id in frames
                result = "Suspicious" if (is_suspicious or is_framed) else "Clean"
                entries.append({"type": "investigate", "target_id": target_id, "result": result})
                try:
                    await player.member.send(f"🔎 **Sheriff:** Your investigation returns: **{result}**")
                except discord.Forbidden:
                    pass
        elif action == "watch":
            visitors = []
            for other_uid, other_data in game.night_actions_queue.items():
                if other_data.get("target") == target_id and other_uid != uid:
                    other_player = game.get_player_by_id(other_uid)
                    if other_player and other_player.alive:
                        visitors.append(other_player)
            visitor_names = ", ".join(v.mention for v in visitors) if visitors else "no one"
            try:
                await player.member.send(f"👁️ **Lookout:** You saw {visitor_names} visit your target last night.")
            except discord.Forbidden:
                pass
        elif action == "duel":
            target = game.get_player_by_id(target_id)
            if target and target.alive:
                winner = resolve_rps(player, target)
                if winner == player:
                    deaths.append((target, "duel"))
                    player.duel_wins += 1
                    entries.append({"type": "duel", "winner_id": player.user_id, "loser_id": target.user_id})
                else:
                    deaths.append((player, "duel"))
                    entries.append({"type": "duel", "winner_id": target.user_id, "loser_id": player.user_id})
        elif action == "swap1":
            first_player_id = uid
            second_player_id = target_id
            for other_uid, other_data in game.night_actions_queue.items():
                if other_data.get("action") == "swap1" and other_uid != uid:
                    second_player_id = other_data.get("target")
            if first_player_id and second_player_id:
                entries.append({"type": "swap", "player1_id": first_player_id, "player2_id": second_player_id})
                for other_uid, other_data in game.night_actions_queue.items():
                    if other_data.get("target") == first_player_id:
                        other_data["target"] = second_player_id
                    elif other_data.get("target") == second_player_id:
                        other_data["target"] = first_player_id
        elif action == "frame":
            frames.add(target_id)
            target_obj = game.get_player_by_id(target_id)
            if target_obj:
                entries.append({"type": "frame", "target_id": target_id})
        elif action == "janitor":
            janitor_target = target_id
            player.janitor_used = True

    mafia_kill_target = None
    for uid, data in game.night_actions_queue.items():
        if data.get("action") == "kill" and uid not in roleblocks:
            player = game.get_player_by_id(uid)
            if player and player.alive:
                target_id = data.get("target")
                target = game.get_player_by_id(target_id)
                if target and target.user_id not in protections and target.user_id not in veteran_alerts:
                    mafia_kill_target = target
                    break

    if mafia_kill_target:
        deaths.append((mafia_kill_target, "mafia_kill"))
        log_entry = {"type": "mafia_kill", "target_id": mafia_kill_target.user_id}
        if janitor_target == mafia_kill_target.user_id:
            log_entry["cleaned"] = True
        entries.append(log_entry)
    elif any(d[1] != "veteran" for d in deaths):
        pass

    for uid, data in game.night_actions_queue.items():
        player = game.get_player_by_id(uid)
        if not player or not player.alive:
            continue
        action = data.get("action")
        target_id = data.get("target")
        if action == "protect":
            if mafia_kill_target and mafia_kill_target.user_id in protections and target_id == mafia_kill_target.user_id:
                entries.append({"type": "protect", "target_id": target_id, "saved": True, "killer_id": uid})

    bh_kill_target = None
    for uid, data in game.night_actions_queue.items():
        if data.get("action") == "bh_kill":
            player = game.get_player_by_id(uid)
            if player and player.alive:
                target_id = data.get("target")
                target = game.get_player_by_id(target_id)
                if target:
                    if target.role == player.bh_target_role:
                        bh_kill_target = target
                        player.bh_killed = True
                    else:
                        player.bh_exposed = True
                    break

    if bh_kill_target:
        deaths.append((bh_kill_target, "bounty_hunter"))
        entries.append({"type": "bh_kill", "target_id": bh_kill_target.user_id})

    for uid in veteran_alerts:
        player = game.get_player_by_id(uid)
        if player:
            player.alerts_used = min(player.alerts_used, 2)

    unique_deaths = []
    seen_ids = set()
    for victim, cause in deaths:
        if victim.user_id not in seen_ids:
            seen_ids.add(victim.user_id)
            unique_deaths.append((victim, cause))

    return unique_deaths, janitor_target, entries
