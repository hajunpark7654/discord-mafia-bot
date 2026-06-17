import asyncio
import discord
from config import NOMINATIONS_REQUIRED, DEFENSE_TIMER, ROLE_EMOJIS


async def run_nomination_phase(game, bot):
    game.nomination_counts = {}
    for player in game.alive_players:
        game.nomination_counts[player.user_id] = []

    for player in game.alive_players:
        await send_nomination_dm(player, game, bot)

    timeout = 10 if getattr(game, 'test_mode', False) else (300 if game.is_auto else 600)
    check_interval = 5
    elapsed = 0
    while elapsed < timeout:
        await asyncio.sleep(min(check_interval, timeout - elapsed))
        elapsed += check_interval
        if getattr(game, '_force_advance', False):
            setattr(game, '_force_advance', False)
            break
        if getattr(game, '_fast_forward', False):
            setattr(game, '_fast_forward', False)
            break
        if getattr(game, '_cancel_token', None) and game._cancel_token.is_set():
            break

    tally = {}
    for nominator_id, targets in game.nomination_counts.items():
        for target_id in targets:
            tally[target_id] = tally.get(target_id, 0) + 1

    if not tally:
        return None

    max_votes = max(tally.values())
    top_candidates = [uid for uid, count in tally.items() if count == max_votes]

    if max_votes < NOMINATIONS_REQUIRED or len(top_candidates) > 1:
        return None

    return top_candidates[0]


async def send_nomination_dm(player, game, bot):
    if (player.is_dummy and not player.is_bot) or not player.member:
        return
    targets = [p for p in game.alive_players if p.user_id != player.user_id]
    if not targets:
        return

    embed = discord.Embed(
        title="🗳️ Day Nomination",
        description="Who do you want to nominate for trial?",
        color=discord.Color.gold()
    )
    options = [discord.SelectOption(label=p.name[:100], value=str(p.user_id)) for p in targets[:25]]
    view = discord.ui.View()
    select = discord.ui.Select(placeholder="Choose a player to nominate...", options=options)

    async def select_callback(interaction):
        if interaction.user.id != player.user_id:
            if not (player.is_bot and interaction.user.id == player.bot_owner_id):
                return
        target_id = int(select.values[0])
        if target_id not in game.nomination_counts.get(player.user_id, []):
            game.nomination_counts.setdefault(player.user_id, []).append(target_id)
        await interaction.response.send_message(f"✅ Nominated <@{target_id}> for trial.", ephemeral=True)

    select.callback = select_callback
    view.add_item(select)
    try:
        await player.member.send(embed=embed, view=view)
    except discord.Forbidden:
        pass


async def run_trial_phase(game, bot, accused_player):
    game.trial_player = accused_player
    game.votes = {}

    channel = game.town_square

    nom_count = sum(1 for targets in game.nomination_counts.values() if accused_player.user_id in targets)

    embed = discord.Embed(
        title=f"⚖️ {accused_player.mention} has been brought to trial! ({nom_count} nomination(s))",
        color=discord.Color.orange()
    )
    await channel.send(embed=embed)

    defense_embed = discord.Embed(
        title=f"🗣️ {accused_player.mention}, you have {DEFENSE_TIMER} seconds to defend yourself!",
        color=discord.Color.blue()
    )
    await channel.send(embed=defense_embed)
    try:
        await accused_player.member.send(f"🗣️ You have {DEFENSE_TIMER} seconds to state your defense in {channel.mention}.")
    except discord.Forbidden:
        pass

    defense_elapsed = 0
    while defense_elapsed < DEFENSE_TIMER:
        await asyncio.sleep(2)
        defense_elapsed += 2
        if getattr(game, '_force_advance', False):
            setattr(game, '_force_advance', False)
            break
        if getattr(game, '_fast_forward', False):
            setattr(game, '_fast_forward', False)
            break

    vote_embed = discord.Embed(
        title=f"🗳️ Is {accused_player.mention} guilty? Check your DMs to vote!",
        color=discord.Color.red()
    )
    await channel.send(embed=vote_embed)

    for player in game.alive_players:
        await send_trial_vote_dm(player, game, bot, accused_player)

    timeout = 10 if getattr(game, 'test_mode', False) else (300 if game.is_auto else 600)
    check_interval = 5
    elapsed = 0
    while elapsed < timeout:
        await asyncio.sleep(min(check_interval, timeout - elapsed))
        elapsed += check_interval
        if getattr(game, '_force_advance', False):
            setattr(game, '_force_advance', False)
            break
        if getattr(game, '_fast_forward', False):
            setattr(game, '_fast_forward', False)
            break
        if getattr(game, '_cancel_token', None) and game._cancel_token.is_set():
            break

    guilty = sum(1 for v in game.votes.values() if v == "guilty")
    innocent = sum(1 for v in game.votes.values() if v == "innocent")
    abstain = sum(1 for v in game.votes.values() if v == "abstain")

    results_embed = discord.Embed(
        title="🗳️ Trial Verdict",
        color=discord.Color.dark_purple()
    )
    results_embed.add_field(name="⚖️ Guilty", value=str(guilty), inline=True)
    results_embed.add_field(name="✅ Innocent", value=str(innocent), inline=True)
    results_embed.add_field(name="⏭️ Abstain", value=str(abstain), inline=True)
    await channel.send(embed=results_embed)

    if guilty > innocent:
        accused_player.alive = False
        return accused_player
    else:
        acquit_embed = discord.Embed(
            title=f"✅ {accused_player.mention} was acquitted!",
            description=f"The town was not convinced ({guilty} guilty vs {innocent} innocent).",
            color=discord.Color.green()
        )
        await channel.send(embed=acquit_embed)
        return None


async def send_trial_vote_dm(player, game, bot, accused):
    if (player.is_dummy and not player.is_bot) or not player.member:
        return
    view = discord.ui.View()
    guilty_btn = discord.ui.Button(label="Guilty", style=discord.ButtonStyle.danger)
    innocent_btn = discord.ui.Button(label="Innocent", style=discord.ButtonStyle.success)
    abstain_btn = discord.ui.Button(label="Abstain", style=discord.ButtonStyle.secondary)

    async def guilty_cb(interaction):
        if interaction.user.id != player.user_id:
            if not (player.is_bot and interaction.user.id == player.bot_owner_id):
                return
        game.votes[player.user_id] = "guilty"
        await interaction.response.send_message("✅ Vote recorded: Guilty", ephemeral=True)

    async def innocent_cb(interaction):
        if interaction.user.id != player.user_id:
            if not (player.is_bot and interaction.user.id == player.bot_owner_id):
                return
        game.votes[player.user_id] = "innocent"
        await interaction.response.send_message("✅ Vote recorded: Innocent", ephemeral=True)

    async def abstain_cb(interaction):
        if interaction.user.id != player.user_id:
            if not (player.is_bot and interaction.user.id == player.bot_owner_id):
                return
        game.votes[player.user_id] = "abstain"
        await interaction.response.send_message("✅ Vote recorded: Abstain", ephemeral=True)

    guilty_btn.callback = guilty_cb
    innocent_btn.callback = innocent_cb
    abstain_btn.callback = abstain_cb

    view.add_item(guilty_btn)
    view.add_item(innocent_btn)
    view.add_item(abstain_btn)

    embed = discord.Embed(
        title=f"🗳️ Trial Vote",
        description=f"Is {accused.mention} guilty or innocent?",
        color=discord.Color.red()
    )
    try:
        await player.member.send(embed=embed, view=view)
    except discord.Forbidden:
        pass
