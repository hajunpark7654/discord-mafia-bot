import os
import random
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
import discord
from discord import Object
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.client import MafiaBot
from bot.database.db import init_db, get_config, set_config
from bot.cards.db import init_card_tables
from bot.cards.spawner import CardSpawner
from bot.commands.admin import setup_admin_commands
from bot.cards.commands import setup_card_commands
from config import (
    GUILD_ID, PRESHOUT_CHANNEL_ID, MIN_PLAYERS,
    RANDOM_AUTO_MIN_INTERVAL, RANDOM_AUTO_MAX_INTERVAL,
    RANDOM_AUTO_JOIN_WINDOW,
)

load_dotenv()

bot = MafiaBot()
scheduler = AsyncIOScheduler()
card_spawner = CardSpawner(bot)

PORT = int(os.getenv("PORT", 8080))

PORT = int(os.getenv("PORT", 8080))


def start_health_server():
    from aiohttp import web

    async def handler(request):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", handler)
    app.router.add_get("/health", handler)
    runner = web.AppRunner(app)

    async def run():
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        print(f"Health server running on port {PORT}")

    return run


async def auto_preshout():
    enabled = get_config("autohost_enabled")
    if enabled != "1":
        return

    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return
    channel = guild.get_channel(PRESHOUT_CHANNEL_ID)
    if not channel:
        return

    from bot.game.engine import GameManager
    manager = GameManager.get_instance()
    if manager.get_game(GUILD_ID):
        return

    game = manager.create_game(GUILD_ID, PRESHOUT_CHANNEL_ID, is_auto=True, is_hosted=False)

    embed = discord.Embed(
        title="🕵️ Mafia — Auto Game!",
        description=(
            f"An automatic game is starting! Click to join.\n"
            f"Roles are assigned by DM.\n"
            f"Needs **{MIN_PLAYERS}+** players. {RANDOM_AUTO_JOIN_WINDOW}s to join."
        ),
        color=discord.Color.dark_red()
    )
    view = discord.ui.View()
    join_btn = discord.ui.Button(label="Join Game", style=discord.ButtonStyle.primary, emoji="🎮")

    async def join_callback(interaction):
        if interaction.user.id in [p.user_id for p in game.players]:
            await interaction.response.send_message("❌ Already joined!", ephemeral=True)
            return
        game.add_player(interaction.user)
        await interaction.response.send_message(f"✅ Joined! ({len(game.players)} players)", ephemeral=True)

    join_btn.callback = join_callback
    view.add_item(join_btn)
    msg = await channel.send(embed=embed, view=view)

    await asyncio.sleep(RANDOM_AUTO_JOIN_WINDOW)

    game = manager.get_game(GUILD_ID)
    if game and len(game.players) >= MIN_PLAYERS:
        await channel.send("🎮 Enough players! Starting auto game...")
        asyncio.create_task(game.start_game(bot))
    elif game:
        await channel.send("❌ Not enough players joined. Auto-game cancelled.")
        manager.remove_game(GUILD_ID)


async def try_schedule_auto():
    await auto_preshout()


@bot.event
async def on_ready():
    print(f"Bot ready: {bot.user}")
    init_db()
    init_card_tables()

    if hasattr(bot, "health_server_coro") and bot.health_server_coro:
        await bot.health_server_coro()
        bot.health_server_coro = None

    await bot.tree.sync(guild=Object(id=GUILD_ID))

    enabled = get_config("autohost_enabled")
    if enabled == "1":
        interval = random.randint(RANDOM_AUTO_MIN_INTERVAL, RANDOM_AUTO_MAX_INTERVAL)
        scheduler.add_job(try_schedule_auto, 'interval', seconds=interval, id='auto_preshout')
        scheduler.start()
        print(f"Auto-host scheduler started (interval: {interval}s)")

    await card_spawner.start()


def main():
    setup_admin_commands(bot)
    setup_card_commands(bot)
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN not found in .env")
        return
    bot.health_server_coro = start_health_server()
    bot.run(token)


if __name__ == "__main__":
    main()
