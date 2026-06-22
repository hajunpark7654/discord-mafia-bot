import os
import random
import asyncio
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
import discord
from discord import Object
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Load .env file only if it exists locally (not needed on Railway)
env_path = Path('.env')
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv()

import sys
print(f"Python {sys.version} | Env vars at module level: {list(os.environ.keys())}", flush=True)

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

PORT = int(os.getenv("PORT", 8080))


def start_health_server():
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import urllib.parse

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/set_token":
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Send a POST to /set_token with body: token=YOUR_TOKEN")
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

        def do_POST(self):
            if self.path == "/set_token":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode()
                params = urllib.parse.parse_qs(body)
                token = params.get("token", [None])[0]
                if token:
                    Path('.env').write_text(f"DISCORD_BOT_TOKEN={token}\n")
                    self.send_response(200)
                    self.send_header("Content-type", "text/plain")
                    self.end_headers()
                    self.wfile.write(b"Token saved to .env")
                else:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Missing 'token' field")
                return
            self.send_response(404)
            self.end_headers()

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

        try:
            guild = Object(id=GUILD_ID)
            existing = await bot.tree.fetch_commands(guild=guild)
            if len(existing) == 0:
                print("No guild commands found, syncing...", flush=True)
                await bot.tree.sync(guild=guild)
                set_config("commands_synced", "1")
                print("Commands synced", flush=True)
            else:
                print(f"Commands exist ({len(existing)} found), skipping sync", flush=True)
        except discord.HTTPException as e:
            print(f"Command sync check failed: {e}", flush=True)

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
    import subprocess

    def load_token():
        # 1) From environment variable (standard)
        t = os.getenv("DISCORD_BOT_TOKEN") or os.getenv("TOKEN")
        if t:
            return t
        # 2) From shell (catches Railway v2 beta where env vars may not pass to os.environ)
        try:
            r = subprocess.run('echo $DISCORD_BOT_TOKEN', shell=True, capture_output=True, text=True, timeout=5)
            t = r.stdout.strip()
            if t:
                return t
        except Exception:
            pass
        # 3) From Railway secret files (beta v2 mounts secrets here)
        for secret_path in ["/railway/secrets/DISCORD_BOT_TOKEN", "/etc/secrets/DISCORD_BOT_TOKEN", "/run/secrets/DISCORD_BOT_TOKEN"]:
            p = Path(secret_path)
            if p.exists():
                t = p.read_text().strip()
                if t:
                    return t
        # 4) From .env file (Console / Start Command)
        env_path = Path('.env')
        if env_path.exists():
            from dotenv import load_dotenv
            load_dotenv()
            return os.getenv("DISCORD_BOT_TOKEN") or os.getenv("TOKEN")
        return None

    token = load_token()
    while not token:
        print(f"ERROR: No token. CWD: {os.getcwd()}, .env exists: {Path('.env').exists()}", flush=True)
        time.sleep(30)
        token = load_token()

    # Write .env so future restarts within the same session find it immediately
    Path('.env').write_text(f"DISCORD_BOT_TOKEN={token}\n")

    start_health_server()
    time.sleep(2)  # let Render health check register

    # Infinite retry with exponential backoff (never gives up)
    delay = 0
    attempt = 0
    while True:
        attempt += 1
        if delay > 0:
            print(f"Rate limited. Waiting {delay}s before attempt {attempt}...", flush=True)
            time.sleep(delay)
        print(f"Connection attempt {attempt}...", flush=True)
        bot = build_bot()
        try:
            bot.run(token)
            return  # bot connected, blocks until disconnect
        except discord.HTTPException as e:
            if e.status == 429:
                print(f"Still rate limited ({e})", flush=True)
                delay = 300 if delay == 0 else min(delay * 2, 7200)  # 5min → 10min → ... → 2hr max
                continue
            print(f"HTTP error: {e}", flush=True)
            return
        except discord.LoginFailure as e:
            print(f"Login failed (invalid token?): {e}", flush=True)
            return
        except Exception as e:
            print(f"Fatal error: {e}", flush=True)
            return


if __name__ == "__main__":
    main()
