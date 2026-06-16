import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from config import (
    ADMIN_USER_ID, PRESHOUT_CHANNEL_ID, MIN_PLAYERS,
    GUILD_ID, POINTS, ROLE_EMOJIS,
)
from bot.game.engine import GameManager
from bot.database.db import add_points, deduct_points, get_leaderboard, get_points, set_config, get_config, wipe_all_points, get_top_player
from bot.client import is_admin


def setup_admin_commands(bot: commands.Bot):
    guild = discord.Object(id=GUILD_ID)

    @bot.tree.command(name="preshout", description="Announce a new game. Players can join.", guild=guild)
    @app_commands.describe(game_type="Game mode (e.g., Mafia)")
    async def preshout(interaction: discord.Interaction, game_type: str = "Mafia"):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin can use this command.", ephemeral=True)
            return

        manager = GameManager.get_instance()
        if manager.get_game(interaction.guild_id):
            await interaction.response.send_message("❌ A game is already in progress!", ephemeral=True)
            return

        game = manager.create_game(interaction.guild_id, interaction.channel_id, game_type=game_type)

        embed = discord.Embed(
            title=f"🕵️ {game_type} — Social deduction!",
            description=(
                f"Roles are assigned by DM when the game starts.\n"
                f"Roles: 🔪 Mafia (eliminate Town at night) · 💉 Doctor (protect one player) · "
                f"🔎 Sheriff (investigate one player) · 🏘️ Town (vote out Mafia during the day)\n"
                f"Needs at least **{MIN_PLAYERS}** players. Click the button to join."
            ),
            color=discord.Color.dark_red()
        )
        view = discord.ui.View()
        join_btn = discord.ui.Button(label="Join Game", style=discord.ButtonStyle.primary, emoji="🎮")

        async def join_callback(btn_interaction: discord.Interaction):
            if btn_interaction.user.id in [p.user_id for p in game.players]:
                await btn_interaction.response.send_message("❌ You already joined!", ephemeral=True)
                return
            player = game.add_player(btn_interaction.user)
            if not player:
                await btn_interaction.response.send_message("❌ Game is not accepting players.", ephemeral=True)
                return
            game.reset_preshout_timer()
            await btn_interaction.response.send_message(f"✅ {btn_interaction.user.mention} joined! ({len(game.players)} players)", ephemeral=True)
            new_desc = f"**{len(game.players)} player(s) have joined.**\n\nNeeds at least **{MIN_PLAYERS}** players. Click the button to join."
            embed.description = new_desc
            await btn_interaction.message.edit(embed=embed)

        join_btn.callback = join_callback
        view.add_item(join_btn)
        game.join_button_active = True
        msg = await interaction.channel.send(embed=embed, view=view)
        game.preshout_message = msg
        game.start_preshout_timer(bot)
        await interaction.response.send_message("✅ Preshout posted!", ephemeral=True)

    @bot.tree.command(name="test", description="Run a test game with a chosen role.", guild=guild)
    @app_commands.describe(role="Optional role to assign yourself (e.g. mafia, doctor, sheriff)")
    async def test_game(interaction: discord.Interaction, role: str = None):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return

        manager = GameManager.get_instance()
        if manager.get_game(interaction.guild_id):
            await interaction.response.send_message("❌ A game is already in progress.", ephemeral=True)
            return

        game = manager.create_game(interaction.guild_id, interaction.channel_id, game_type="Mafia")
        if role:
            game._test_role = role.lower().strip()
        await interaction.response.send_message("🧪 Starting test game...", ephemeral=True)
        asyncio.create_task(game.start_test_game(bot, interaction.user))

    @bot.tree.command(name="start", description="Start the game as host (you spectate) or auto (you play).", guild=guild)
    @app_commands.describe(mode="'auto' to play, or leave blank to host")
    async def start(interaction: discord.Interaction, mode: str = None):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin can use this command.", ephemeral=True)
            return

        manager = GameManager.get_instance()
        game = manager.get_game(interaction.guild_id)
        if not game:
            await interaction.response.send_message("❌ No game in progress. Use /preshout first.", ephemeral=True)
            return

        if len(game.players) < MIN_PLAYERS:
            await interaction.response.send_message(f"❌ Need at least {MIN_PLAYERS} players. ({len(game.players)} joined)", ephemeral=True)
            return

        is_auto = mode == "auto"
        game.is_auto = is_auto
        game.is_hosted = True

        if is_auto:
            game.add_player(interaction.user)

        await interaction.response.send_message("🎮 Game is starting...", ephemeral=True)
        asyncio.create_task(game.start_game(bot))

    @bot.tree.command(name="close", description="Close the last game's channels and category.", guild=guild)
    async def close_channels(interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        manager = GameManager.get_instance()
        cleanup = manager.get_last_cleanup()
        if not cleanup:
            await interaction.followup.send("❌ No previous game channels to close.", ephemeral=True)
            return

        guild = cleanup["guild"]
        deleted = 0

        if cleanup["town_square"]:
            try:
                await cleanup["town_square"].delete()
                deleted += 1
            except:
                pass
        if cleanup["mafia_den"]:
            try:
                await cleanup["mafia_den"].delete()
                deleted += 1
            except:
                pass
        if cleanup["dead_chat"]:
            try:
                await cleanup["dead_chat"].delete()
                deleted += 1
            except:
                pass
        if cleanup["player_role"]:
            try:
                await cleanup["player_role"].delete()
                deleted += 1
            except:
                pass
        if cleanup["dead_role"]:
            try:
                await cleanup["dead_role"].delete()
                deleted += 1
            except:
                pass
        if cleanup["category"]:
            try:
                await cleanup["category"].delete()
                deleted += 1
            except:
                pass

        manager.clear_last_cleanup()
        await interaction.followup.send(f"✅ Cleaned up {deleted} items.", ephemeral=True)

    @bot.tree.command(name="end", description="Cancel a preshout or end an active game.", guild=guild)
    async def end_game(interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        manager = GameManager.get_instance()
        game = manager.get_game(interaction.guild_id)
        if not game:
            await interaction.followup.send("❌ No active preshout or game.", ephemeral=True)
            return

        if game.state == "lobby":
            await game.cancel_lobby(bot, "Cancelled by admin.")
            await interaction.followup.send("✅ Preshout cancelled.", ephemeral=True)
        else:
            try:
                await game.end_game(bot, "admin_ended")
                await interaction.followup.send("✅ Game ended.", ephemeral=True)
            except Exception as e:
                print(f"END ERROR: {e}")
                GameManager.get_instance().remove_game(interaction.guild_id)
                await interaction.followup.send(f"⚠️ Game force-cleaned.", ephemeral=True)

    @bot.tree.command(name="force_night", description="Force advance to night phase.", guild=guild)
    async def force_night(interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin can use this command.", ephemeral=True)
            return
        manager = GameManager.get_instance()
        game = manager.get_game(interaction.guild_id)
        if not game:
            await interaction.response.send_message("❌ No active game.", ephemeral=True)
            return
        game._force_advance = True
        await interaction.response.send_message("⏩ Advancing to night...", ephemeral=True)

    @bot.tree.command(name="force_day", description="Force advance to day phase.", guild=guild)
    async def force_day(interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin can use this command.", ephemeral=True)
            return
        manager = GameManager.get_instance()
        game = manager.get_game(interaction.guild_id)
        if not game:
            await interaction.response.send_message("❌ No active game.", ephemeral=True)
            return
        game._force_advance = True
        game._force_day = True
        await interaction.response.send_message("⏩ Advancing to day...", ephemeral=True)

    @bot.tree.command(name="force_vote", description="Force close voting phase.", guild=guild)
    async def force_vote(interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin can use this command.", ephemeral=True)
            return
        manager = GameManager.get_instance()
        game = manager.get_game(interaction.guild_id)
        if not game:
            await interaction.response.send_message("❌ No active game.", ephemeral=True)
            return
        game._force_advance = True
        await interaction.response.send_message("⏩ Closing votes...", ephemeral=True)

    @bot.tree.command(name="autohost", description="Toggle random auto-hosted games.", guild=guild)
    @app_commands.describe(action="'toggle' to enable/disable")
    async def autohost(interaction: discord.Interaction, action: str = "toggle"):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        current = get_config("autohost_enabled") or "0"
        new_val = "0" if current == "1" else "1"
        set_config("autohost_enabled", new_val)
        status = "enabled" if new_val == "1" else "disabled"
        await interaction.response.send_message(f"✅ Auto-host {status}.", ephemeral=True)

    @bot.tree.command(name="add_points", description="Add points to a user.", guild=guild)
    @app_commands.describe(user="The user", amount="Points to add")
    async def add_p(interaction: discord.Interaction, user: discord.User, amount: int):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        add_points(user.id, amount)
        await interaction.response.send_message(f"✅ Added {amount} points to {user.mention}.", ephemeral=True)

    @bot.tree.command(name="deduct_points", description="Deduct points from a user.", guild=guild)
    @app_commands.describe(user="The user", amount="Points to deduct")
    async def deduct_p(interaction: discord.Interaction, user: discord.User, amount: int):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        deduct_points(user.id, amount)
        await interaction.response.send_message(f"✅ Deducted {amount} points from {user.mention}.", ephemeral=True)

    @bot.tree.command(name="leaderboard", description="Show points leaderboard.", guild=guild)
    async def lb(interaction: discord.Interaction):
        rows = get_leaderboard()
        if not rows:
            await interaction.response.send_message("No points data yet.", ephemeral=True)
            return
        embed = discord.Embed(
            title="🏆 Points Leaderboard",
            color=discord.Color.gold(),
            description="Top 10 players by total points"
        )
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(rows[:10], 1):
            user = bot.get_user(row["user_id"])
            name = user.display_name if user else f"<@{row['user_id']}>"
            medal = medals[i - 1] if i <= 3 else f"`{i}.`"
            wr = f" ({row['games_won']}/{row['games_played']}W)" if row['games_played'] > 0 else ""
            embed.add_field(
                name=f"{medal} {name}",
                value=f"╰ {row['points']} pts{wr}",
                inline=False
            )
        embed.set_footer(text="🏆 Points Leaderboard • Updated live")
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="wipe_points", description="Wipe ALL points for all users. Admin only.", guild=guild)
    async def wipe_pts(interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        wipe_all_points()
        await interaction.followup.send("✅ All points wiped.", ephemeral=True)

    @bot.tree.command(name="points", description="Check your or another's points.", guild=guild)
    @app_commands.describe(user="User to check (optional)")
    async def pts(interaction: discord.Interaction, user: discord.User = None):
        target = user or interaction.user
        data = get_points(target.id)
        await interaction.response.send_message(
            f"💰 {target.mention} has **{data['points']}** points "
            f"({data['games_played']} games, {data['games_won']} wins).",
            ephemeral=True
        )
