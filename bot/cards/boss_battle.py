import asyncio
import random
import discord
from discord import ButtonStyle
from bot.cards.db import insert_card_instance, get_player_cards
from bot.cards.models import generate_card, compute_ovr, combat_damage, RARITY_COLORS
from bot.database.db import add_points

active_boss = {}


class BossBattle:
    def __init__(self, bot, channel, card_template, admin):
        self.bot = bot
        self.channel = channel
        self.template = card_template
        self.admin = admin
        self.players = []
        self.player_cards = {}
        self.boss_hp = 0
        self.boss_max_hp = 0
        self.boss_atk = card_template["attack"]
        self.boss_spd = card_template["speed"]
        self.turn = 0
        self.damage_dealt = {}
        self.state = "joining"
        self.enraged = False
        self.BASE_DMG_MULT = 2
        self.ENRAGED_DMG_MULT = 1.5
        self.msg = None

    def effective_boss_atk(self):
        atk = self.boss_atk * self.BASE_DMG_MULT
        if self.enraged:
            atk = round(atk * self.ENRAGED_DMG_MULT)
        return atk

    def scale_hp(self):
        count = len(self.players)
        multiplier = 10 if count < 6 else 13
        self.boss_max_hp = self.template["health"] * multiplier
        self.boss_hp = self.boss_max_hp

    def _mention(self, pid_or_user_id):
        m = self.bot.get_user(pid_or_user_id)
        return m.mention if m else f"<@{pid_or_user_id}>"

    async def run(self):
        active_boss[self.channel.id] = self
        try:
            embed = discord.Embed(
                title=f"👹 Boss Battle: {self.template['name']}!",
                description=(
                    f"**{self.template['name']}** appears with massive power!\n\n"
                    f"**HP:** {self.template['health']}  **ATK:** {self.template['attack']}  **SPD:** {self.template['speed']}\n"
                    f"Click **Join Battle** to bring your best card!\n"
                    f"5 minutes to join."
                ),
                color=0xFF0000,
            )
            if self.template.get("image_url"):
                embed.set_image(url=self.template["image_url"])

            view = discord.ui.View(timeout=300)

            join_button = discord.ui.Button(label="Join Battle", style=ButtonStyle.primary, emoji="⚔️")

            async def join_cb(interaction):
                if interaction.user.id in self.players:
                    await interaction.response.send_message("❌ Already joined!", ephemeral=True)
                    return
                cards = get_player_cards(interaction.user.id)
                if not cards:
                    await interaction.response.send_message("❌ You need at least 1 card!", ephemeral=True)
                    return
                self.players.append(interaction.user.id)
                count = len(self.players)
                await interaction.response.send_message(f"✅ Joined! ({count} players)", ephemeral=True)

            join_button.callback = join_cb
            view.add_item(join_button)

            skip_button = discord.ui.Button(label="Skip Timer", style=ButtonStyle.secondary, emoji="⏩")

            async def skip_cb(interaction):
                if interaction.user.id != self.admin.id:
                    await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
                    return
                self.skipped = True
                await interaction.response.send_message("⏩ Timer skipped!", ephemeral=True)

            skip_button.callback = skip_cb
            view.add_item(skip_button)

            cancel_button = discord.ui.Button(label="Cancel", style=ButtonStyle.danger, emoji="⛔")

            async def cancel_cb(interaction):
                if interaction.user.id != self.admin.id:
                    await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
                    return
                self.skipped = True
                self.cancelled = True
                await interaction.response.send_message("⛔ Boss battle cancelled!", ephemeral=True)

            cancel_button.callback = cancel_cb
            view.add_item(cancel_button)

            self.msg = await self.channel.send(
                content="**👹 Boss Battle!** Join to fight!",
                embed=embed, view=view,
                allowed_mentions=discord.AllowedMentions(everyone=True)
            )

        except discord.Forbidden:
            try:
                self.msg = await self.channel.send(
                    content="**👹 Boss Battle!** Join to fight!",
                    embed=embed, view=view,
                )
            except Exception as e:
                print(f"Boss battle setup failed (no perms): {e}", flush=True)
                del active_boss[self.channel.id]
                return
        except Exception as e:
            print(f"Boss battle setup failed: {e}", flush=True)
            del active_boss[self.channel.id]
            return

        self.cancelled = False
        self.skipped = False
        for _ in range(300):
            if self.skipped:
                break
            await asyncio.sleep(1)

        if self.cancelled:
            await self.msg.edit(content="⛔ Boss battle cancelled.", embed=None, view=None)
            del active_boss[self.channel.id]
            return

        if len(self.players) < 1:
            await self.msg.edit(content="❌ Not enough players joined.", embed=None, view=None)
            del active_boss[self.channel.id]
            return

        self.scale_hp()

        await self.channel.send("📬 **Check your DMs to pick your boss battle card!** (60s to choose)")

        pick_tasks = {}
        pending = 0
        for pid in self.players:
            cards = get_player_cards(pid)
            member = self.bot.get_user(pid)
            name = member.display_name if member else str(pid)
            if not cards:
                continue
            if len(cards) == 1:
                card = dict(cards[0])
                card["max_health"] = card["health"]
                self.player_cards[pid] = card
                continue

            task = {"chosen": None, "cards": cards, "name": name}
            pick_tasks[pid] = task
            pending += 1

            embed = discord.Embed(
                title=f"🎴 Choose your boss battle card!",
                description=f"Pick the card you'll fight **{self.template['name']}** with.\nYou have 60 seconds.",
                color=0x00FF00,
            )
            options = [discord.SelectOption(
                label=f"{c['card_name']} [{c['rarity']}] HP:{c['health']} ATK:{c['attack']} SPD:{c['speed']}"[:100],
                value=str(c["id"])
            ) for c in cards[:25]]

            view = discord.ui.View(timeout=70)
            select = discord.ui.Select(placeholder="Choose your card...", options=options)

            async def select_cb(interaction, pid=pid, cards=cards):
                if interaction.user.id != pid:
                    await interaction.response.send_message("❌ Not your card selection!", ephemeral=True)
                    return
                chosen_id = int(interaction.data["values"][0])
                pick_tasks[pid]["chosen"] = chosen_id
                card_name = next(c["card_name"] for c in cards if c["id"] == chosen_id)
                await interaction.response.edit_message(content=f"✅ Selected **{card_name}**!", embed=None, view=None)

            select.callback = select_cb
            view.add_item(select)

            try:
                await member.send(embed=embed, view=view)
            except:
                await self.channel.send(f"{self._mention(pid)} — choose your card:", embed=embed, view=view)

        if pending > 0:
            await self.channel.send(f"⏳ Waiting for {pending} player(s) to pick a card...")
            for _ in range(60):
                if all(t["chosen"] is not None for t in pick_tasks.values()):
                    break
                await asyncio.sleep(1)

        for pid, task in pick_tasks.items():
            if task["chosen"] is not None:
                c = next((c for c in task["cards"] if c["id"] == task["chosen"]), None)
                if c:
                    card = dict(c)
                    card["max_health"] = card["health"]
                    self.player_cards[pid] = card
            else:
                await self.channel.send(f"⏰ {task['name']} timed out! Auto-selecting first card.")
                card = dict(task["cards"][0])
                card["max_health"] = card["health"]
                self.player_cards[pid] = card

        player_lines = []
        for pid in self.players:
            pc = self.player_cards.get(pid)
            if pc:
                player_lines.append(
                    f"• {self._mention(pid)} — **{pc['card_name']}** [{pc['rarity']}] HP: {pc['health']}/{pc['max_health']}"
                )
            else:
                player_lines.append(f"• {self._mention(pid)} — No card")
        await self.channel.send(f"👥 **Players:**\n" + "\n".join(player_lines))

        await self.msg.edit(
            content=f"⚔️ **Boss Battle Starting!** {len(self.players)} players. Boss HP: **{self.boss_hp}**",
            embed=None, view=None
        )

        await self.channel.send(
            f"⚔️ **{len(self.players)}** players vs **{self.template['name']}**! "
            f"Boss HP: **{self.boss_hp}**  Boss ATK: **{self.effective_boss_atk()}** (2x multiplier)"
        )

        for pid in self.players:
            self.damage_dealt[pid] = 0

        while self.boss_hp > 0:
            alive = [pid for pid in self.players if self.player_cards.get(pid, {}).get("health", 0) > 0]
            if not alive:
                break

            self.turn += 1

            round_lines = [f"**── Round {self.turn} ──**"]

            target = random.choice(alive)
            card = self.player_cards.get(target, {})
            dmg, crit, dtype, dodged = combat_damage(self.effective_boss_atk(), card.get("speed", 0))
            if dtype == "miss":
                round_lines.append(f"👹 **{self.template['name']}** attacks {self._mention(target)}'s **{card.get('card_name','?')}** but **misses**!")
            elif dtype == "dodge":
                round_lines.append(f"👹 **{self.template['name']}** attacks {self._mention(target)}'s **{card.get('card_name','?')}** but it **dodges**!")
            else:
                card["health"] = card.get("health", 1) - dmg
                crit_text = " **CRIT!**" if crit else ""
                round_lines.append(f"👹 **{self.template['name']}** attacks {self._mention(target)}'s **{card.get('card_name','?')}** for **{dmg}** damage!{crit_text}")

            if card.get("health", 0) <= 0:
                round_lines.append(f"💀 {self._mention(target)}'s **{card.get('card_name','?')}** has been defeated!")

            if not self.enraged and self.boss_hp <= self.boss_max_hp // 2:
                self.enraged = True
                round_lines.append(f"🔥 **{self.template['name']}** is **ENRAGED**! Damage increased by 1.5x (3x total)!")

            if self.turn % 3 == 0 and self.boss_hp > 0:
                heal = min(1000, self.boss_max_hp - self.boss_hp)
                self.boss_hp += heal
                for pid in alive:
                    pc = self.player_cards.get(pid, {})
                    pc["health"] = max(0, pc.get("health", 0) - 800)
                round_lines.append(f"💀 **Life Steal!** Boss heals **{heal}** HP, deals **800** damage to all remaining players!")

            if self.turn % 6 == 0 and self.boss_hp > 0:
                revived = 0
                for pid in self.players:
                    pc = self.player_cards.get(pid, {})
                    if pc.get("health", 0) <= 0:
                        pc["health"] = round(pc.get("max_health", 1) / 2)
                        revived += 1
                if revived > 0:
                    round_lines.append(f"🔄 **Revival!** {revived} fallen players revived with half HP!")

            if self.boss_hp <= 0:
                round_lines.append(f"🎉 **The boss has been defeated!**")
                await self.channel.send("\n".join(round_lines))
                break

            spd_order = sorted(
                [(pid, self.player_cards[pid]) for pid in alive if self.player_cards[pid].get("health", 0) > 0],
                key=lambda x: x[1].get("speed", 0), reverse=True
            )
            for pid, pc in spd_order:
                dmg, crit, dtype, dodged = combat_damage(pc.get("attack", 1))
                if dtype in ("miss", "dodge"):
                    round_lines.append(f"⚔️ {self._mention(pid)}'s **{pc.get('card_name','?')}** attacks but **{dtype}s**!")
                    continue
                actual = min(dmg, self.boss_hp)
                self.boss_hp -= actual
                self.damage_dealt[pid] += actual
                crit_text = " **CRIT!**" if crit else ""
                round_lines.append(f"⚔️ {self._mention(pid)}'s **{pc['card_name']}** deals **{actual}** damage!{crit_text} (Boss HP: {max(0, self.boss_hp)})")
                if self.boss_hp <= 0:
                    round_lines.append(f"🎉 **The boss has been defeated!**")
                    break

            await self.channel.send("\n".join(round_lines))
            if self.boss_hp > 0:
                await asyncio.sleep(3)

        if self.boss_hp <= 0:
            winner = max(self.damage_dealt, key=self.damage_dealt.get)
            await self.channel.send(f"🎉 **Victory!** The boss has been defeated!")
            summary = "\n".join(
                f"• {self._mention(pid)}: {dmg} damage"
                for pid, dmg in sorted(self.damage_dealt.items(), key=lambda x: -x[1])
            )
            await self.channel.send(f"**Damage Summary:**\n{summary}")

            reward_log = []
            for pid in self.players:
                member = self.bot.get_user(pid)
                reward_log.append(f"• {self._mention(pid)}: +20 points")
                if pid == winner:
                    add_points(pid, 20)
                    card = generate_card(self.template, from_mafia=False)
                    card["is_mythical"] = random.random() < 0.15
                    card["is_shiny"] = not card["is_mythical"] and random.random() < 0.35
                    card["ovr"] = compute_ovr(card["health"], card["attack"], card["speed"])
                    cid = insert_card_instance(
                        owner_id=pid,
                        template_id=card["template_id"],
                        health=card["health"],
                        attack=card["attack"],
                        speed=card["speed"],
                        h_mod=card["health_mod"],
                        a_mod=card["attack_mod"],
                        s_mod=card["speed_mod"],
                        is_shiny=card["is_shiny"],
                        is_mythical=card["is_mythical"],
                        rarity=card["rarity"],
                        ovr=card["ovr"],
                        is_special=card.get("is_special", False),
                    )
                    shiny_s = " ✨" if card["is_shiny"] else ""
                    mythical_s = " 🌌" if card["is_mythical"] else ""
                    card_name = self.template["name"]
                    reward_log[-1] += f" + **{card_name}** [{card['rarity']}]{shiny_s}{mythical_s}"

                    lines = [f"{self._mention(pid)}, you earned **{card_name}** [{card['rarity']}]{shiny_s}{mythical_s} as the MVP!"]
                    if card["is_shiny"]:
                        lines.append("✨ This card RADIATES a golden-aura.")
                    if card["is_mythical"]:
                        lines.append("🌌 The air tenses, as a mythical aura emits from the card.")
                    lines.append(f"**HP:** {card['health']}  **ATK:** {card['attack']}  **SPD:** {card['speed']}")
                    lines.append(f"**OVR:** {card['ovr']}")

                    img = ""
                    if card["is_mythical"]:
                        img = self.template.get("mythical_catch_image_url") or ""
                    if not img and card["is_shiny"]:
                        img = self.template.get("shiny_catch_image_url") or ""
                    if not img:
                        img = self.template.get("catch_image_url") or ""

                    card_color = 0xFFD700 if card["is_shiny"] else (0x000000 if card["is_mythical"] else RARITY_COLORS.get(card["rarity"], 0x808080))
                    card_embed = discord.Embed(
                        title=f"🏆 MVP Reward: {card_name} [{card['rarity']}]{shiny_s}{mythical_s}",
                        description="\n".join(lines),
                        color=card_color,
                    )
                    if img:
                        card_embed.set_image(url=img)
                    await self.channel.send(embed=card_embed)

                    if member:
                        try:
                            await member.send(f"🏆 MVP! You defeated the boss and won **{card_name}** [{card['rarity']}]{shiny_s}{mythical_s} +**20** points!")
                        except:
                            pass
                else:
                    add_points(pid, 20)
                    if member:
                        try:
                            await member.send(f"🏆 You helped defeat the boss! +**20** points!")
                        except:
                            pass

            await self.channel.send(f"**Rewards:**\n" + "\n".join(reward_log))
        else:
            await self.channel.send(f"💀 **Defeat!** All players have fallen.")
            summary = "\n".join(
                f"• {self.bot.get_user(pid).mention if self.bot.get_user(pid) else '<@'+str(pid)+'>'}: {dmg} damage"
                for pid, dmg in sorted(self.damage_dealt.items(), key=lambda x: -x[1])
            )
            await self.channel.send(f"**Damage Summary:**\n{summary}")

        del active_boss[self.channel.id]
