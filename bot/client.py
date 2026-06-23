import discord
from discord.ext import commands
from config import GUILD_ID, ADMIN_USER_ID


class MafiaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents, allowed_mentions=discord.AllowedMentions(everyone=True))

    async def setup_hook(self):
        await self.tree.sync(guild=discord.Object(id=GUILD_ID))

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print(f"Guild ID: {GUILD_ID}")
        print("------")


def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.id == ADMIN_USER_ID or interaction.user.guild_permissions.administrator
