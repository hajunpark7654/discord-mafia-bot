import asyncio
import random
import discord
from bot.cards.db import get_player_cards, get_card_instance, finish_battle
from bot.cards.models import combat_damage, RARITY_COLORS

BATTLE_TIMEOUT = 60
_battle_locks = set()


def hp_bar(current, maximum, length=10):
    ratio = max(0, current / maximum) if maximum > 0 else 0
    filled = round(ratio * length)
    bar = "🟩" * filled + "⬛" * (length - filled)
    return f"{bar} {max(0,current)}/{maximum}"


class CardBattle:
    def __init__(self, battle_id, player1, player2, p1_cards, p2_cards):
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
        pids = list(self.players.keys())
        return len(self.alive_cards(pids[0])) == 0 or len(self.alive_cards(pids[1])) == 0

    def get_winner(self):
        pids = list(self.players.keys())
        if len(self.alive_cards(pids[0])) == 0:
            return pids[1]
        if len(self.alive_cards(pids[1])) == 0:
            return pids[0]
        return None

    def get_valid_targets(self, attacker_owner_id):
        opponent_id = [uid for uid in self.players if uid != attacker_owner_id][0]
        return self.alive_cards(opponent_id)


async def run_battle(bot, battle_id, player1, player2, guild, channel):
    _battle_locks.add(player1.id)
    _battle_locks.add(player2.id)
    try:
        await _run_battle(bot, battle_id, player1, player2, guild, channel)
    finally:
        _battle_locks.discard(player1.id)
        _battle_locks.discard(player2.id)


async def _run_battle(bot, battle_id, player1, player2, guild, channel):
    p1_cards = get_player_cards(player1.id)[:25]
    p2_cards = get_player_cards(player2.id)[:25]
    if len(p1_cards) < 3 or len(p2_cards) < 3:
        await channel.send(f"❌ {player1.mention} or {player2.mention} don't have 3 cards to battle!")
        return

    battle = CardBattle(battle_id, player1, player2, p1_cards, p2_cards)

    await channel.send(embed=discord.Embed(
        title=f"⚔️ Battle: {player1.display_name} vs {player2.display_name}",
        color=0xFF4500,
    ))

    # Simultaneous ephemeral card selection
    pending_pids = [player1.id, player2.id]
    pick_results = {}

    async def card_select_btn_cb(interaction):
        pid = interaction.user.id
        if pid not in pending_pids:
            await interaction.response.send_message("❌ You're not in this battle!", ephemeral=True)
            return
        if pid in pick_results:
            await interaction.response.send_message("✅ Already picked your cards!", ephemeral=True)
            return

        cards = get_player_cards(pid)
        if len(cards) < 3:
            await interaction.response.send_message("❌ You need 3 cards!", ephemeral=True)
            return

        options = [discord.SelectOption(
            label=f"{c['card_name']} [{c['rarity']}] HP:{c['health']} ATK:{c['attack']} SPD:{c['speed']}"[:100],
            value=str(c["id"])
        ) for c in cards[:25]]

        select_view = discord.ui.View(timeout=120)
        select = discord.ui.Select(placeholder="Pick 3 cards...", options=options, max_values=3)

        async def inner_select(inner_interaction):
            if inner_interaction.user.id != pid:
                await inner_interaction.response.send_message("❌ Not yours!", ephemeral=True)
                return
            chosen = [int(v) for v in inner_interaction.data["values"]]
            pick_results[pid] = chosen
            pending_pids.remove(pid)
            await inner_interaction.response.edit_message(content=f"✅ Selected {len(chosen)} cards!", embed=None, view=None)

        select.callback = inner_select
        select_view.add_item(select)
        await interaction.response.send_message("🎴 Pick your 3 cards:", view=select_view, ephemeral=True)

    pick_view = discord.ui.View(timeout=120)
    pick_btn = discord.ui.Button(label="Select Cards", style=discord.ButtonStyle.primary, emoji="🎴")
    pick_btn.callback = card_select_btn_cb
    pick_view.add_item(pick_btn)
    pick_msg = await channel.send(
        f"🎴 {player1.mention} **vs** {player2.mention} — click to pick your cards!",
        view=pick_view
    )

    for _ in range(120):
        if not pending_pids:
            break
        await asyncio.sleep(1)

    # Resolve picks
    for pid in [player1.id, player2.id]:
        if pid not in pick_results:
            cards = get_player_cards(pid)
            member = battle.players[pid]["member"]
            await channel.send(f"⏰ {member.display_name} timed out! Auto-selecting first 3 cards.")
            pick_results[pid] = [c["id"] for c in cards[:3]]

    p1_chosen = [c for c in p1_cards if c["id"] in pick_results[player1.id]][:3]
    p2_chosen = [c for c in p2_cards if c["id"] in pick_results[player2.id]][:3]

    for c in p1_chosen:
        c["_max_health"] = c["health"]
    for c in p2_chosen:
        c["_max_health"] = c["health"]
    battle.players[player1.id]["cards"] = p1_chosen
    battle.players[player2.id]["cards"] = p2_chosen
    battle._build_turn_order()

    # Clean up pick button
    for item in pick_view.children:
        item.disabled = True
    await pick_msg.edit(content=f"🎴 Cards selected! Battle starting...", view=pick_view)

    # Lineup embed
    def format_lineup(pid):
        pdata = battle.players[pid]
        lines = []
        for c in pdata["cards"]:
            lines.append(f"• {c['card_name']} [{c['rarity']}] {hp_bar(c['health'], c['health'])}")
        return "\n".join(lines)

    lineup_embed = discord.Embed(
        title=f"🎴 Lineup",
        description=f"**{player1.display_name}**\n{format_lineup(player1.id)}\n\n**{player2.display_name}**\n{format_lineup(player2.id)}",
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
            action = f"⚔️ **{card['card_name']}** ({owner.display_name}) → "
            if dtype == "miss":
                action += f"☁️ Misses **{target['card_name']}**"
            elif dtype == "dodge":
                action += f"💨 **{target['card_name']}** dodges!"
            else:
                target["health"] -= dmg
                crit_text = " 💥**CRIT!**" if crit else ""
                action += f"**{target['card_name']}** **-{dmg}**{crit_text}"
            actions.append(action)

            if target["health"] <= 0:
                actions.append(f"💀 **{target['card_name']}** defeated!")

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

        round_embed.description = "\n".join(actions) if actions else "No actions."
        round_embed.add_field(name="📊 Status", value="\n\n".join(status_lines), inline=False)
        await channel.send(embed=round_embed)
        await asyncio.sleep(2)

    winner_id = battle.get_winner()
    if winner_id:
        finish_battle(battle_id, winner_id)
        winner_member = battle.players[winner_id]["member"]
        await channel.send(embed=discord.Embed(
            title=f"🏆 {winner_member.display_name} wins!",
            color=0xFFD700,
        ))


async def _pick_target_ephemeral(player, card, targets, channel):
    chosen_target = [None]

    view = discord.ui.View(timeout=BATTLE_TIMEOUT)
    btn = discord.ui.Button(label=f"Target for {card['card_name']}", style=discord.ButtonStyle.danger, emoji="🎯")

    async def btn_cb(interaction):
        if interaction.user.id != player.id:
            await interaction.response.send_message("❌ Not your turn!", ephemeral=True)
            return

        options = [discord.SelectOption(
            label=f"{t['card_name']} [{t['rarity']}] HP:{t['health']}",
            value=str(t["id"])
        ) for t in targets[:25]]

        select_view = discord.ui.View(timeout=BATTLE_TIMEOUT)
        select = discord.ui.Select(placeholder="Choose target...", options=options)

        async def select_cb(inner_interaction):
            if inner_interaction.user.id != player.id:
                await inner_interaction.response.send_message("❌ Not yours!", ephemeral=True)
                return
            chosen_id = int(inner_interaction.data["values"][0])
            chosen_target[0] = chosen_id
            t_name = next((t["card_name"] for t in targets if t["id"] == chosen_id), "?")
            await inner_interaction.response.edit_message(content=f"✅ Targeting **{t_name}**!", embed=None, view=None)

        select.callback = select_cb
        select_view.add_item(select)
        await interaction.response.send_message("🎯 Pick your target:", view=select_view, ephemeral=True)

    btn.callback = btn_cb
    view.add_item(btn)
    msg = await channel.send(f"🎯 {player.mention}, target for **{card['card_name']}**", view=view)

    for _ in range(BATTLE_TIMEOUT):
        await asyncio.sleep(1)
        if chosen_target[0] is not None:
            for item in view.children:
                item.disabled = True
            t_name = next((t["card_name"] for t in targets if t["id"] == chosen_target[0]), "?")
            await msg.edit(content=f"✅ Targeting **{t_name}**", view=view)
            return next((t for t in targets if t["id"] == chosen_target[0]), None)

    await channel.send(f"⏰ {player.display_name}'s target selection timed out!")
    for item in view.children:
        item.disabled = True
    await msg.edit(content=f"⏰ Timed out", view=view)
    return None
