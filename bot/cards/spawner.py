import asyncio
import random
import discord
from discord import Embed, ButtonStyle
from bot.cards.models import generate_card
from bot.cards.db import get_random_template, insert_card_instance, get_all_templates
from bot.database.db import get_config, set_config
from config import GUILD_ID

SPAWN_MIN_INTERVAL = 300
SPAWN_MAX_INTERVAL = 600
CATCH_TIMEOUT = 120


class CardSpawner:
    def __init__(self, bot):
        self.bot = bot
        self._task = None
        self.spawn_channel_id = None

    async def start(self):
        self.spawn_channel_id = get_config("card_spawn_channel")
        if self.spawn_channel_id:
            self.spawn_channel_id = int(self.spawn_channel_id)
        if not self.spawn_channel_id:
            print("Card spawner: no spawn channel configured")
            return
        if get_config("card_spawn_enabled") != "1":
            print("Card spawner: disabled")
            return
        self._task = asyncio.create_task(self._spawn_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            self._task = None

    async def _spawn_loop(self):
        while True:
            interval = random.randint(SPAWN_MIN_INTERVAL, SPAWN_MAX_INTERVAL)
            await asyncio.sleep(interval)
            try:
                await self._spawn_card()
            except Exception as e:
                print(f"Card spawn error: {e}")

    async def _spawn_card(self):
        channel = self.bot.get_channel(self.spawn_channel_id)
        if not channel:
            return

        template = get_random_template()
        if not template:
            print("Card spawner: no templates")
            return

        embed = Embed(
            title=f"🌟 A wild card appeared!",
            description=f"**{template['name']}**\n\nFirst to catch it gets the card!",
            color=0x00FF00,
        )
        if template.get("catch_image_url"):
            embed.set_image(url=template["catch_image_url"])

        view = CatchView(template, self.bot)
        msg = await channel.send(embed=embed, view=view)
        view.message = msg

        await asyncio.sleep(CATCH_TIMEOUT)
        if not view.caught:
            view.disable_all_items()
            await msg.edit(content="⏰ The card got away...", view=view)


class CatchView(discord.ui.View):
    def __init__(self, template, bot):
        super().__init__(timeout=CATCH_TIMEOUT)
        self.template = template
        self.bot = bot
        self.caught = False
        self.message = None

    @discord.ui.button(label="Catch!", style=ButtonStyle.primary, emoji="🎴")
    async def catch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.caught:
            await interaction.response.send_message("❌ Already caught!", ephemeral=True)
            return

        self.caught = True
        await interaction.response.defer(ephemeral=True)
        self.disable_all_items()
        if self.message:
            await self.message.edit(content="🎴 Card caught!", view=self)

        try:
            card = generate_card(self.template, from_mafia=False)
            card_id = insert_card_instance(
                owner_id=interaction.user.id,
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
            )

            lines = [f"Congratulations, {interaction.user.mention}!"]
            lines.append(f"You caught **{self.template['name']}**!")
            mod_parts = []
            if card["health_mod"] != 0:
                mod_parts.append(f"{'+' if card['health_mod'] > 0 else ''}{card['health_mod']*100:.1f}% health")
            if card["attack_mod"] != 0:
                mod_parts.append(f"{'+' if card['attack_mod'] > 0 else ''}{card['attack_mod']*100:.1f}% attack")
            if card["speed_mod"] != 0:
                mod_parts.append(f"{'+' if card['speed_mod'] > 0 else ''}{card['speed_mod']*100:.1f}% speed")
            if mod_parts:
                lines.append(f"Modifiers: {', '.join(mod_parts)}")
            if card["is_shiny"]:
                lines.append("✨ This card **RADIATES** a golden aura.")
            if card["is_mythical"]:
                lines.append("🌌 The air tenses, as a mythical aura emits from the card.")
            if card["rarity"] == "S":
                lines.append("💭 You feel empowered, as memories of the past flow through your mind.")
            lines.append(f"Rarity: **{card['rarity']}** | OVR: **{card['ovr']}**")

            embed = Embed(
                title="🎴 Card Acquired!",
                description="\n".join(lines),
                color=0xFFD700 if card["is_shiny"] else (0x000000 if card["is_mythical"] else 0x00FF00),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            button.disabled = True
        except Exception as e:
            self.caught = False
            print(f"Card catch error: {e}")
            if self.message:
                await self.message.edit(content="❌ Error catching card. Try again.", view=self)
            try:
                await interaction.followup.send("❌ An error occurred while catching the card.", ephemeral=True)
            except:
                pass
