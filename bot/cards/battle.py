import asyncio
import random
import discord
from bot.cards.db import get_player_cards, get_card_instance, finish_battle
from bot.cards.models import combat_damage

BATTLE_TIMEOUT = 60


class CardBattle:
    def __init__(self, battle_id, player1, player2, p1_cards, p2_cards):
        self.battle_id = battle_id
        self.players = {player1.id: {"member": player1, "cards": p1_cards},
                        player2.id: {"member": player2, "cards": p2_cards}}
        self.turn_order = []
        self._build_turn_order()

    def _build_turn_order(self):
        pids = list(self.players.keys())
        # Separate by player, sort each by SPD descending
        p1_cards = sorted(self.players[pids[0]]["cards"], key=lambda c: c["speed"], reverse=True)
        p2_cards = sorted(self.players[pids[1]]["cards"], key=lambda c: c["speed"], reverse=True)
        # Interleave: highest SPD overall goes first, then alternate
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


async def run_battle(bot, battle_id, player1, player2, guild):
    p1_cards = get_player_cards(player1.id)[:3]
    p2_cards = get_player_cards(player2.id)[:3]
    if len(p1_cards) < 3 or len(p2_cards) < 3:
        await player1.send("❌ You or your opponent don't have 3 cards to battle!")
        return

    battle = CardBattle(battle_id, player1, player2, p1_cards, p2_cards)

    async def pick_cards_for_player(player, cards, label):
        embed = discord.Embed(title=f"🎴 Choose your 3 cards for battle!", color=0x00FF00)
        options = []
        for c in cards[:25]:
            label_text = f"{c['card_name']} [{c['rarity']}] HP:{c['health']} ATK:{c['attack']} SPD:{c['speed']}"
            options.append(discord.SelectOption(label=label_text[:100], value=str(c["id"])))
        view = discord.ui.View()
        select = discord.ui.Select(placeholder="Select 3 cards...", options=options, max_values=3)
        chosen = []

        async def select_cb(interaction):
            if interaction.user.id != player.id:
                return
            nonlocal chosen
            chosen = [int(v) for v in select.values]
            await interaction.response.send_message(f"✅ Selected {len(chosen)} cards!", ephemeral=True)

        select.callback = select_cb
        view.add_item(select)
        await player.send(embed=embed, view=view)

        for _ in range(30):
            await asyncio.sleep(1)
            if len(chosen) == 3:
                return chosen
        await player.send("⏰ Timed out! Auto-selecting first 3 cards.")
        return [c["id"] for c in cards[:3]]

    p1_selected = await pick_cards_for_player(player1, p1_cards, "Your cards")
    p2_selected = await pick_cards_for_player(player2, p2_cards, "Opponent's cards")

    p1_chosen = [c for c in p1_cards if c["id"] in p1_selected][:3]
    p2_chosen = [c for c in p2_cards if c["id"] in p2_selected][:3]

    battle.players[player1.id]["cards"] = p1_chosen
    battle.players[player2.id]["cards"] = p2_chosen
    battle._build_turn_order()

    channel = None
    if guild:
        channel = guild.system_channel or guild.text_channels[0] if guild.text_channels else None

    turn_num = 0
    while not battle.is_finished():
        turn_num += 1
        alive_this_pass = [c for c in battle.turn_order if c["health"] > 0]

        for phase in range(2):
            for card in alive_this_pass:
                if card["health"] <= 0:
                    continue
                owner_id = card["_owner"]
                owner = battle.players[owner_id]["member"]
                targets = battle.get_valid_targets(owner_id)
                if not targets:
                    break

                target = await _pick_target(owner, card, targets)
                if target is None:
                    target = random.choice(targets)

                dmg, crit, dtype, dodged = combat_damage(card["attack"], target.get("speed", 0))
                if dtype == "miss":
                    status = f"⚔️ **{card['card_name']}** ({owner.display_name}) attacks **{target['card_name']}** but **misses**!"
                elif dtype == "dodge":
                    status = f"⚔️ **{card['card_name']}** ({owner.display_name}) attacks **{target['card_name']}** but it **dodges**!"
                else:
                    target["health"] -= dmg
                    crit_text = " **CRIT!**" if crit else ""
                    status = f"⚔️ **{card['card_name']}** ({owner.display_name}) attacks **{target['card_name']}** for **{dmg}** damage!{crit_text} (HP: {max(0, target['health'])})"
                if channel:
                    await channel.send(status)
                else:
                    try:
                        await owner.send(status)
                    except:
                        pass

                if target["health"] <= 0:
                    ko_msg = f"💀 **{target['card_name']}** has been defeated!"
                    if channel:
                        await channel.send(ko_msg)
                    else:
                        try:
                            await owner.send(ko_msg)
                        except:
                            pass

    winner_id = battle.get_winner()
    if winner_id:
        finish_battle(battle_id, winner_id)
        winner_member = battle.players[winner_id]["member"]
        msg = f"🏆 **{winner_member.display_name}** wins the battle!"
        if channel:
            await channel.send(msg)
        try:
            await winner_member.send(msg)
        except:
            pass
        loser_id = [uid for uid in battle.players if uid != winner_id][0]
        loser_member = battle.players[loser_id]["member"]
        try:
            await loser_member.send(f"😔 You lost the battle against {winner_member.display_name}.")
        except:
            pass


async def _pick_target(player, card, targets):
    embed = discord.Embed(
        title=f"⚔️ Choose your target",
        description=f"**{card['card_name']}** (HP:{card['health']} ATK:{card['attack']}) is attacking!\nPick a target:",
        color=0xFF0000,
    )
    options = [discord.SelectOption(label=f"{t['card_name']} [{t['rarity']}] HP:{t['health']}", value=str(t["id"])) for t in targets[:25]]

    view = discord.ui.View()
    select = discord.ui.Select(placeholder="Select target...", options=options)
    chosen_target = [None]

    async def select_cb(interaction):
        if interaction.user.id != player.id:
            return
        chosen_target[0] = int(select.values[0])
        await interaction.response.send_message(f"🎯 Attacking {select.values[0]}!", ephemeral=True)

    select.callback = select_cb
    view.add_item(select)
    try:
        await player.send(embed=embed, view=view)
    except:
        return None

    for _ in range(BATTLE_TIMEOUT):
        await asyncio.sleep(1)
        if chosen_target[0] is not None:
            return next((t for t in targets if t["id"] == chosen_target[0]), None)
    try:
        await player.send("⏰ Target selection timed out!")
    except:
        pass
    return None
