import asyncio
import random
import discord
from discord import ButtonStyle
from bot.cards.db import get_random_template, insert_card_instance, get_player_cards
from bot.cards.models import generate_card, compute_ovr
from bot.database.db import add_points


def combat_damage(attack):
    if random.random() < 0.10:
        return 0, False
    reduction = random.randint(0, 10) / 100
    dmg = max(1, round(attack * (1 - reduction)))
    crit = random.random() < 0.05
    if crit:
        dmg = round(dmg * 1.5)
    return dmg, crit


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

    def scale_hp(self):
        count = len(self.players)
        multiplier = 7 if count < 6 else 10
        self.boss_max_hp = self.template["health"] * multiplier
        self.boss_hp = self.boss_max_hp

    async def run(self):
        try:
            embed = discord.Embed(
                title=f"👹 Boss Battle: {self.template['name']}!",
                description=(
                    f"A wild **{self.template['name']}** appears with massive power!\n\n"
                    f"Click join to bring your best card!\n"
                    f"5 minutes to join."
                ),
                color=0xFF0000,
            )
            view = discord.ui.View()
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

            msg = await self.channel.send(
                content="@everyone 👹 A **Boss Battle** has started! Join to fight!",
                embed=embed, view=view
            )
        except Exception as e:
            print(f"Boss battle setup failed: {e}", flush=True)
            return

        await asyncio.sleep(300)

        if len(self.players) < 1:
            await msg.edit(content="❌ Not enough players joined.", embed=None, view=None)
            return

        self.scale_hp()

        for pid in self.players:
            cards = get_player_cards(pid)[:1]
            if cards:
                self.player_cards[pid] = cards[0]
            member = self.bot.get_user(pid)
            if member and cards:
                try:
                    await member.send(f"⚔️ Boss Battle! Your card **{cards[0]['card_name']}** will fight!")
                except:
                    pass

        await msg.edit(content=f"⚔️ **Boss Battle Starting!** {len(self.players)} players. Boss HP: {self.boss_hp}", embed=None, view=None)

        for pid in self.players:
            self.damage_dealt[pid] = 0

        while self.boss_hp > 0:
            alive = [pid for pid in self.players if self.player_cards.get(pid, {}).get("health", 0) > 0]
            if not alive:
                break

            self.turn += 1

            target = random.choice(alive)
            dmg, crit = combat_damage(self.boss_atk)
            card = self.player_cards.get(target, {})
            card["health"] = card.get("health", 1) - dmg
            crit_text = " **CRIT!**" if crit else ""
            if dmg > 0:
                await self.channel.send(f"👹 **{self.template['name']}** attacks {self.bot.get_user(target).mention if self.bot.get_user(target) else '<@'+str(target)+'>'}'s **{card.get('card_name','?')}** for **{dmg}** damage!{crit_text}")
            else:
                await self.channel.send(f"👹 **{self.template['name']}** attacks but misses {self.bot.get_user(target).mention if self.bot.get_user(target) else '<@'+str(target)+'>'}'s **{card.get('card_name','?')}**!")

            if card.get("health", 0) <= 0:
                await self.channel.send(f"💀 {self.bot.get_user(target).mention if self.bot.get_user(target) else '<@'+str(target)+'>'}'s **{card.get('card_name','?')}** has been defeated!")

            if self.turn % 3 == 0 and self.boss_hp > 0:
                heal = min(1000, self.boss_max_hp - self.boss_hp)
                self.boss_hp += heal
                for pid in alive:
                    pc = self.player_cards.get(pid, {})
                    pc["health"] = max(0, pc.get("health", 0) - 600)
                await self.channel.send(f"💀 **Life Steal!** The boss heals **{heal}** HP and deals **600** damage to all remaining players!")

            if self.turn % 5 == 0 and self.boss_hp > 0:
                revived = 0
                for pid in self.players:
                    pc = self.player_cards.get(pid, {})
                    if pc.get("health", 0) <= 0:
                        pc["health"] = round(pc.get("max_health", 1) / 2)
                        revived += 1
                if revived > 0:
                    await self.channel.send(f"🔄 **Revival!** {revived} fallen players revived with half HP!")

            if self.boss_hp <= 0:
                break

            for pid in alive:
                pc = self.player_cards.get(pid, {})
                if pc.get("health", 0) <= 0:
                    continue
                atk = pc.get("attack", 1)
                stack_atk = 0
                for _ in range(2):
                    dmg, crit = combat_damage(atk)
                    if dmg == 0:
                        self.boss_hp -= 0
                    else:
                        actual = min(dmg, self.boss_hp)
                        self.boss_hp -= actual
                        stack_atk += actual
                        self.damage_dealt[pid] += actual
                    if self.boss_hp <= 0:
                        break
                if stack_atk > 0:
                    member = self.bot.get_user(pid)
                    mention = member.mention if member else f"<@{pid}>"
                    crit_text = "" if not any(True for _ in range(0) if random.random() < 0) else ""
                    await self.channel.send(f"⚔️ {mention}'s **{pc['card_name']}** deals **{stack_atk}** damage to **{self.template['name']}**! (Boss HP: {max(0, self.boss_hp)})")
                if self.boss_hp <= 0:
                    break

        if self.boss_hp <= 0:
            winner = max(self.damage_dealt, key=self.damage_dealt.get)
            await self.channel.send(f"🎉 **Victory!** The boss has been defeated!")
            summary = "\n".join(
                f"• {self.bot.get_user(pid).mention if self.bot.get_user(pid) else '<@'+str(pid)+'>'}: {dmg} damage"
                for pid, dmg in sorted(self.damage_dealt.items(), key=lambda x: -x[1])
            )
            await self.channel.send(f"**Damage Summary:**\n{summary}")

            for pid in self.players:
                if pid == winner:
                    add_points(pid, 30)
                    card = generate_card(self.template, from_mafia=False)
                    card["is_shiny"] = random.random() < 0.35
                    card["is_mythical"] = random.random() < 0.05
                    card["health"], card["attack"], card["speed"] = card["health"], card["attack"], card["speed"]
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
                    member = self.bot.get_user(pid)
                    if member:
                        shiny_s = " ✨" if card["is_shiny"] else ""
                        mythical_s = " 🌌" if card["is_mythical"] else ""
                        try:
                            await member.send(f"🏆 MVP! You won the boss card **{card['card_name']}** [{card['rarity']}]{shiny_s}{mythical_s} and **30** points!")
                        except:
                            pass
                else:
                    add_points(pid, 20)
                    member = self.bot.get_user(pid)
                    if member:
                        try:
                            await member.send(f"🏆 You helped defeat the boss! +**20** points!")
                        except:
                            pass
        else:
            await self.channel.send(f"💀 **Defeat!** All players have fallen.")
            summary = "\n".join(
                f"• {self.bot.get_user(pid).mention if self.bot.get_user(pid) else '<@'+str(pid)+'>'}: {dmg} damage"
                for pid, dmg in sorted(self.damage_dealt.items(), key=lambda x: -x[1])
            )
            await self.channel.send(f"**Damage Summary:**\n{summary}")
