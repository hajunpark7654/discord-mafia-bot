import asyncio
import random
import discord
from bot.cards.db import get_player_cards, get_card_instance, finish_battle
from bot.cards.models import combat_damage, RARITY_COLORS

BATTLE_TIMEOUT = 60


def hp_bar(current, maximum, length=10):
    ratio = max(0, current / maximum) if maximum > 0 else 0
    filled = round(ratio * length)
    bar = "🟩" * filled + "⬛" * (length - filled)
    return f"{bar} {max(0,current)}/{maximum}"


class CardBattle:
    def __init__(self, battle_id, player1, player2, p1_cards, p2_cards):
        self.battle_id = battle_id
        self.players = {player1.id: {"member": player1, "cards": p1_cards},
                        player2.id: {"member": player2, "cards": p2_cards}}
        self.turn_order = []
        self._build_turn_order()

    def _build_turn_order(self):
        pids = list(self.players.keys())
        p1_cards = sorted(self.players[pids[0]]["cards"], key=lambda c: c["speed"], reverse=True)
        p2_cards = sorted(self.players[pids[1]]["cards"], key=lambda c: c["speed"], reverse=True)
        order = []
        i1 = i2 = 0
        turn_p1 = p1_cards[0]["speed"] >= p2_cards[0]["speed"] if p1_cards and p2_cards else bool(p1_cards)
        while i1 < len(p1_cards) or i2 < len(p2_cards):
            if turn_p1 and i1 < len(p1_cards):
                p1_cards[i1]["_owner"] = pids[0]
                order.append(p1_cards[i1])
                i1 += 1
            elif not turn_p1 and i2 < len(p2_cards):
                p2_cards[i2]["_owner"] = pids[1]
                order.append(p2_cards[i2])
                i2 += 1
            turn_p1 = not turn_p1
        self.turn_order = order

    def alive_cards(self, owner_id):
        return [c for c in self.players[owner_id]["cards"] if c["health"] > 0]

    def is_finished(self):
        return len(self.alive_cards(self.players[list(self.players.keys())[0]]["member"].id)) == 0 or \
               len(self.alive_cards(self.players[list(self.players.keys())[1]]["member"].id)) == 0

    def get_winner(self):
        p1_id = list(self.players.keys())[0]
        p2_id = list(self.players.keys())[1]
        if len(self.alive_cards(p1_id)) == 0:
            return p2_id
        if len(self.alive_cards(p2_id)) == 0:
            return p1_id
        return None

    def get_valid_targets(self, attacker_owner_id):
        opponent_id = [uid for uid in self.players if uid != attacker_owner_id][0]
        return self.alive_cards(opponent_id)


async def run_battle(bot, battle_id, player1, player2, guild, channel):
    p1_cards = get_player_cards(player1.id)[:25]
    p2_cards = get_player_cards(player2.id)[:25]
    if len(p1_cards) < 3 or len(p2_cards) < 3:
        await channel.send(f"❌ {player1.mention} or {player2.mention} don't have 3 cards to battle!")
        return

    battle = CardBattle(battle_id, player1, player2, p1_cards, p2_cards)

    arena_embed = discord.Embed(
        title=f"⚔️ Battle Arena",
        description=f"{player1.mention} **vs** {player2.mention}",
        color=0xFF4500,
    )
    arena_msg = await channel.send(embed=arena_embed)

    # ephemeral card selection
    async def pick_cards_ephemeral(player, cards):
        options = [discord.SelectOption(
            label=f"{c['card_name']} [{c['rarity']}] HP:{c['health']} ATK:{c['attack']} SPD:{c['speed']}"[:100],
            value=str(c["id"])
        ) for c in cards[:25]]

        view = discord.ui.View(timeout=120)
        select = discord.ui.Select(placeholder="Select 3 cards...", options=options, max_values=3)
        chosen = []

        async def select_cb(interaction):
            if interaction.user.id != player.id:
                await interaction.response.send_message("❌ Not your selection!", ephemeral=True)
                return
            nonlocal chosen
            chosen = [int(v) for v in interaction.data["values"]]
            await interaction.response.edit_message(
                content=f"✅ Selected {len(chosen)} cards!",
                embed=None, view=None
            )

        select.callback = select_cb
        view.add_item(select)
        await channel.send(f"🎴 {player.mention}, choose your cards:", view=view)

        for _ in range(120):
            await asyncio.sleep(1)
            if len(chosen) == 3:
                return chosen
        await channel.send(f"⏰ {player.display_name} timed out! Auto-selecting first 3 cards.")
        return [c["id"] for c in cards[:3]]

    p1_selected = await pick_cards_ephemeral(player1, p1_cards)
    p2_selected = await pick_cards_ephemeral(player2, p2_cards)

    p1_chosen = [c for c in p1_cards if c["id"] in p1_selected][:3]
    p2_chosen = [c for c in p2_cards if c["id"] in p2_selected][:3]

    for c in p1_chosen:
        c["_max_health"] = c["health"]
    for c in p2_chosen:
        c["_max_health"] = c["health"]
    battle.players[player1.id]["cards"] = p1_chosen
    battle.players[player2.id]["cards"] = p2_chosen
    battle._build_turn_order()

    # Lineup display
    p1_lines = "\n".join(f"• {c['card_name']} [{c['rarity']}] {hp_bar(c['health'],c['health'])}" for c in p1_chosen)
    p2_lines = "\n".join(f"• {c['card_name']} [{c['rarity']}] {hp_bar(c['health'],c['health'])}" for c in p2_chosen)

    lineup_embed = discord.Embed(
        title=f"🎴 Lineup",
        description=f"**{player1.display_name}**\n{p1_lines}\n\n**{player2.display_name}**\n{p2_lines}",
        color=0xFF4500,
    )
    await channel.send(embed=lineup_embed)

    turn_num = 0
    while not battle.is_finished():
        turn_num += 1
        alive_this_pass = [c for c in battle.turn_order if c["health"] > 0]

        round_embed = discord.Embed(
            title=f"⚔️ Round {turn_num}",
            color=0xFF4500,
        )
        actions = []
        defeated = []

        for card in alive_this_pass:
            if card["health"] <= 0:
                continue
            owner_id = card["_owner"]
            owner = battle.players[owner_id]["member"]
            targets = battle.get_valid_targets(owner_id)
            if not targets:
                break

            target = await _pick_target_ephemeral(owner, card, targets, channel)
            if target is None:
                target = random.choice(targets)

            dmg, crit, dtype, dodged = combat_damage(card["attack"], target.get("speed", 0))
            if dtype == "miss":
                actions.append(f"⚔️ **{card['card_name']}** → ☁️ Misses **{target['card_name']}**")
            elif dtype == "dodge":
                actions.append(f"⚔️ **{card['card_name']}** → 💨 **{target['card_name']}** dodges!")
            else:
                target["health"] -= dmg
                crit_text = " 💥**CRIT!**" if crit else ""
                actions.append(f"⚔️ **{card['card_name']}** → **{target['card_name']}** **{dmg}** dmg{crit_text}")

            if target["health"] <= 0:
                defeated.append(target["card_name"])
                actions.append(f"💀 **{target['card_name']}** defeated!")

        # Show HP statuses
        status_lines = []
        for pid, pdata in battle.players.items():
            member = pdata["member"]
            lines = []
            for c in pdata["cards"]:
                max_hp = c.get("_max_health", c["health"])
                if c["health"] <= 0:
                    lines.append(f"~~{c['card_name']}~~ 💀")
                else:
                    lines.append(f"{c['card_name']} {hp_bar(c['health'], max_hp)}")
            status_lines.append(f"**{member.display_name}**\n" + "\n".join(lines))

        round_embed.description = "\n".join(actions) if actions else "No actions this round."
        round_embed.add_field(name="📊 Status", value="\n\n".join(status_lines), inline=False)
        await channel.send(embed=round_embed)
        await asyncio.sleep(2)

    winner_id = battle.get_winner()
    if winner_id:
        finish_battle(battle_id, winner_id)
        winner_member = battle.players[winner_id]["member"]
        win_embed = discord.Embed(
            title=f"🏆 {winner_member.display_name} wins!",
            color=0xFFD700,
        )
        await channel.send(embed=win_embed)


async def _pick_target_ephemeral(player, card, targets, channel):
    embed = discord.Embed(
        title=f"🎯 Choose target",
        description=f"**{card['card_name']}** (HP:{card['health']} ATK:{card['attack']}) is attacking!",
        color=0xFF0000,
    )
    options = [discord.SelectOption(label=f"{t['card_name']} [{t['rarity']}] HP:{t['health']}", value=str(t["id"])) for t in targets[:25]]

    view = discord.ui.View(timeout=60)
    select = discord.ui.Select(placeholder="Select target...", options=options)
    chosen_target = [None]

    async def select_cb(interaction):
        if interaction.user.id != player.id:
            await interaction.response.send_message("❌ Not your turn!", ephemeral=True)
            return
        chosen_id = int(interaction.data["values"][0])
        chosen_target[0] = chosen_id
        t_name = next((t["card_name"] for t in targets if t["id"] == chosen_id), str(chosen_id))
        await interaction.response.edit_message(
            content=f"🎯 Targeting **{t_name}**!",
            embed=None, view=None
        )

    select.callback = select_cb
    view.add_item(select)
    msg = await channel.send(f"{player.mention}, choose your target:", embed=embed, view=view)

    for _ in range(BATTLE_TIMEOUT):
        await asyncio.sleep(1)
        if chosen_target[0] is not None:
            return next((t for t in targets if t["id"] == chosen_target[0]), None)

    await channel.send(f"⏰ {player.display_name}'s target selection timed out!")
    return None
