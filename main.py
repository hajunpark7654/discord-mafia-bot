import os
import random
import asyncio
import time
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
import discord
from discord import Object
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

PORT = int(os.getenv("PORT", 8080))


def start_health_server():
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"Health server running on port {PORT}", flush=True)


def build_bot():
    bot = MafiaBot()
    bot.card_spawner = CardSpawner(bot)

    @bot.event
    async def on_ready():
        print(f"Bot ready: {bot.user}", flush=True)
        init_db()
        init_card_tables()

        if get_config("commands_synced") != "1":
            try:
                await bot.tree.sync(guild=Object(id=GUILD_ID))
                set_config("commands_synced", "1")
                print("Commands synced")
            except discord.HTTPException as e:
                if e.status == 429:
                    print(f"Rate limited during sync, will retry on next restart. ({e})")
                else:
                    print(f"Sync failed: {e}")
        else:
            print("Commands already synced, skipping")

        enabled = get_config("autohost_enabled")
        if enabled == "1":
            scheduler = AsyncIOScheduler()
            interval = random.randint(RANDOM_AUTO_MIN_INTERVAL, RANDOM_AUTO_MAX_INTERVAL)
            from bot.game.engine import GameManager

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
                manager = GameManager.get_instance()
                if manager.get_game(GUILD_ID):
                    return
                game = manager.create_game(GUILD_ID, PRESHOUT_CHANNEL_ID, is_auto=True, is_hosted=False)
                embed = discord.Embed(
                    title="🕵️ Mafia — Auto Game!",
                    description=f"An automatic game is starting! Click to join.\nRoles are assigned by DM.\nNeeds **{MIN_PLAYERS}+** players. {RANDOM_AUTO_JOIN_WINDOW}s to join.",
                    color=discord.Color.dark_red(),
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

            scheduler.add_job(auto_preshout, 'interval', seconds=interval, id='auto_preshout')
            scheduler.start()
            print(f"Auto-host scheduler started (interval: {interval}s)")

        await bot.card_spawner.start()

    setup_admin_commands(bot)
    setup_card_commands(bot)
    return bot


def main():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN not found in .env")
        return

    start_health_server()

    # Wait 2 minutes before first connection to let any rate limit clear
    print("Waiting 120s before connecting to Discord...", flush=True)
    time.sleep(120)

    for attempt in range(5):
        try:
            bot = build_bot()
            bot.run(token)
            break
        except discord.HTTPException as e:
            if e.status == 429:
                wait = 60 * (attempt + 1)
                print(f"Rate limited (429), retry {attempt + 1}/5 in {wait}s...", flush=True)
                time.sleep(wait)
                continue
            raise
        except Exception as e:
            print(f"Fatal error: {e}", flush=True)
            raise


if __name__ == "__main__":
    main()
