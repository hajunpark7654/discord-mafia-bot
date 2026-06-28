import asyncio
import random
import discord
from discord import Embed, ButtonStyle
from bot.cards.models import generate_card
from bot.cards.db import get_random_template, insert_card_instance, get_all_templates
from bot.database.db import get_config, set_config
from config import GUILD_ID

CATCH_TIMEOUT = 120


def get_spawn_interval():
    min_s = int(get_config("spawn_min_interval") or 600)
    max_s = int(get_config("spawn_max_interval") or 900)
    if max_s < min_s:
        max_s = min_s
    return min_s, max_s


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
            if get_config("card_spawn_enabled") != "1":
                await asyncio.sleep(60)
                continue
            min_s, max_s = get_spawn_interval()
            interval = random.randint(min_s, max_s)
            await asyncio.sleep(interval)
            if get_config("card_spawn_enabled") != "1":
                continue
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
        if template.get("image_url"):
            embed.set_image(url=template["image_url"])

        view = CatchView(template, self.bot)
        msg = await channel.send(embed=embed, view=view)
        view.message = msg

        await asyncio.sleep(CATCH_TIMEOUT)
        if not view.caught:
            for item in view.children:
                item.disabled = True
            await msg.edit(content="⏰ The card got away...", view=view)


class CatchView(discord.ui.View):
    def __init__(self, template, bot):
        super().__init__(timeout=CATCH_TIMEOUT)
        self.template = template
        self.bot = bot
        self.caught = False
        self.message = None
        self.override_card = None

    @discord.ui.button(label="Catch!", style=ButtonStyle.primary, emoji="🎴")
    async def catch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.caught:
            await interaction.response.send_message("❌ Already caught!", ephemeral=True)
            return

        self.caught = True
        for item in self.children:
            item.disabled = True
        self.message = interaction.message
        await interaction.response.edit_message(content="🎴 Card caught!", view=self)

        asyncio.create_task(self._process_catch(interaction))

    async def _process_catch(self, interaction: discord.Interaction):
        try:
            card = self.override_card if self.override_card else generate_card(self.template, from_mafia=False)
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
                is_special=card.get("is_special", False),
            )

            mod_parts = []
            if card["speed_mod"] != 0:
                mod_parts.append(f"{'+' if card['speed_mod'] > 0 else ''}{card['speed_mod']*100:.1f}% speed")
            if card["attack_mod"] != 0:
                mod_parts.append(f"{'+' if card['attack_mod'] > 0 else ''}{card['attack_mod']*100:.1f}% attack")
            if card["health_mod"] != 0:
                mod_parts.append(f"{'+' if card['health_mod'] > 0 else ''}{card['health_mod']*100:.1f}% health")

            congrats = f"Congratulations, {interaction.user.mention}, You caught **{self.template['name']}**"
            if mod_parts:
                congrats += f" with modifiers: {', '.join(mod_parts)}"
            else:
                congrats += "!"
            lines = [congrats]

            if card["is_shiny"]:
                lines.append("✨ This card RADIATES a golden-aura.")
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
            img = ""
            if card["is_mythical"]:
                img = self.template.get("mythical_catch_image_url") or ""
            if not img and card["is_shiny"]:
                img = self.template.get("shiny_catch_image_url") or ""
            if not img:
                img = self.template.get("catch_image_url") or ""
            if img:
                embed.set_image(url=img)

            await interaction.followup.send(embed=embed)
        except Exception as e:
            self.caught = False
            for item in self.children:
                item.disabled = False
            print(f"Card catch error: {e}")
            import traceback
            traceback.print_exc()
            if self.message:
                await self.message.edit(content="❌ Error catching card. Try again.", view=self)
            try:
                await interaction.followup.send(f"❌ An error occurred: {e}", ephemeral=True)
            except:
                pass

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        print(f"CatchView on_error: {error}")
        import traceback
        traceback.print_exc()
        self.caught = False
        try:
            await interaction.response.send_message(f"❌ {error}", ephemeral=True)
        except:
            pass
