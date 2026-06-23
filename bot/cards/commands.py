import discord
from typing import Optional
from discord import app_commands
from discord.ext import commands
from config import GUILD_ID, ADMIN_USER_ID
from bot.client import is_admin
from bot.cards.db import (
    get_player_cards, get_card_instance, transfer_card,
    get_all_templates, get_completion, get_owned_template_ids,
    add_card_template, delete_card_template, create_battle, insert_card_instance,
)
from bot.cards.models import generate_card, RARITY_COLORS, compute_ovr, compute_rarity, apply_modifiers
from bot.cards.battle import run_battle
from bot.cards.spawner import CatchView, CATCH_TIMEOUT


async def card_autocomplete(interaction: discord.Interaction, current: str):
    cards = get_player_cards(interaction.user.id)
    result = []
    for c in cards:
        if current.lower() not in c["card_name"].lower() and not (current.isdigit() and str(c["id"]).startswith(current)):
            continue
        mods = ""
        parts = []
        if c["health_mod"]: parts.append(f"HP{c['health_mod']*100:+.0f}%")
        if c["attack_mod"]: parts.append(f"ATK{c['attack_mod']*100:+.0f}%")
        if c["speed_mod"]: parts.append(f"SPD{c['speed_mod']*100:+.0f}%")
        if parts: mods = f" ({', '.join(parts)})"
        name = f"{'✨' if c['is_shiny'] else ''}{'🌌' if c['is_mythical'] else ''}{c['card_name']} [{c['rarity']}]{mods}"
        result.append(app_commands.Choice(name=name[:100], value=str(c["id"])))
        if len(result) >= 25:
            break
    return result


async def template_autocomplete(interaction: discord.Interaction, current: str):
    templates = get_all_templates()
    if not templates:
        return []
    current_lower = current.lower()
    matches = [t for t in templates if current_lower in t["name"].lower()]
    return [
        app_commands.Choice(name=f"{t['name']} [{t['rarity']}]", value=t["name"])
        for t in matches[:25]
    ]


def setup_card_commands(bot: commands.Bot):
    guild = discord.Object(id=GUILD_ID)

    @bot.tree.command(name="card", description="View card info", guild=guild)
    @app_commands.describe(card_id="Card ID to inspect")
    @app_commands.autocomplete(card_id=card_autocomplete)
    async def card_info(interaction: discord.Interaction, card_id: str):
        card = get_card_instance(int(card_id))
        if not card:
            await interaction.response.send_message("❌ Card not found.", ephemeral=True)
            return
        if card["owner_id"] != interaction.user.id and not is_admin(interaction):
            await interaction.response.send_message("❌ You don't own this card.", ephemeral=True)
            return

        color = 0x000000 if card["is_mythical"] else RARITY_COLORS.get(card["rarity"], 0x808080)

        desc_parts = []
        if card["is_shiny"]:
            desc_parts.append("✨ This card is a shiny!")
        if card["is_mythical"]:
            desc_parts.append("🌌 This card exudes a mythical aura!")

        def fmt_mod(mod):
            if mod == 0:
                return ""
            return f" ({mod*100:+.1f}%)"

        stats_line = f"HP: {card['health']}{fmt_mod(card['health_mod'])}    ATK: {card['attack']}{fmt_mod(card['attack_mod'])}    SPD: {card['speed']}{fmt_mod(card['speed_mod'])}"

        footer_parts = [stats_line]
        footer_parts.append(f"OVR: {card['ovr']}")

        embed = discord.Embed(
            title=f"{'✨ ' if card['is_shiny'] else ''}{'🌌 ' if card['is_mythical'] else ''}{card['card_name']}",
            description="\n".join(desc_parts),
            color=color,
        )
        img = ""
        if card["is_mythical"]:
            img = card.get("mythical_catch_image_url") or ""
        if not img and card["is_shiny"]:
            img = card.get("shiny_catch_image_url") or ""
        if not img:
            img = card.get("catch_image_url") or ""
        if img:
            embed.set_image(url=img)
        embed.set_footer(text="\n".join(footer_parts))
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="card_give", description="Give a card to another player", guild=guild)
    @app_commands.describe(player="Recipient", card_id="Card to give")
    @app_commands.autocomplete(card_id=card_autocomplete)
    async def card_give(interaction: discord.Interaction, player: discord.User, card_id: str):
        card = get_card_instance(int(card_id))
        if not card or card["owner_id"] != interaction.user.id:
            await interaction.response.send_message("❌ You don't own this card.", ephemeral=True)
            return
        transfer_card(int(card_id), player.id)
        await interaction.response.send_message(f"✅ Gave **{card['card_name']}** to {player.mention}!", ephemeral=True)

    @bot.tree.command(name="card_list", description="List your cards", guild=guild)
    @app_commands.describe(sort="Sort by (rarity, shiny, mythical)")
    async def card_list(interaction: discord.Interaction, sort: str = None):
        cards = get_player_cards(interaction.user.id)
        if not cards:
            await interaction.response.send_message("You don't have any cards yet!", ephemeral=True)
            return

        if sort == "shiny":
            cards = [c for c in cards if c["is_shiny"]] + [c for c in cards if not c["is_shiny"]]
        elif sort == "mythical":
            cards = [c for c in cards if c["is_mythical"]] + [c for c in cards if not c["is_mythical"]]

        class CardListPaginator(discord.ui.View):
            def __init__(self, cards, user_id):
                super().__init__(timeout=120)
                self.cards = cards
                self.user_id = user_id
                self.per_page = 30
                self.total_pages = max(1, (len(cards) + self.per_page - 1) // self.per_page)
                self.page = 1

            def build_embed(self):
                start = (self.page - 1) * self.per_page
                page_cards = self.cards[start:start + self.per_page]
                lines = []
                for c in page_cards:
                    tag = ""
                    if c["is_shiny"]: tag += "✨"
                    if c["is_mythical"]: tag += "🌌"
                    mods = ""
                    parts = []
                    if c["health_mod"]: parts.append(f"HP{c['health_mod']*100:+.0f}%")
                    if c["attack_mod"]: parts.append(f"ATK{c['attack_mod']*100:+.0f}%")
                    if c["speed_mod"]: parts.append(f"SPD{c['speed_mod']*100:+.0f}%")
                    if parts: mods = f" ({', '.join(parts)})"
                    lines.append(f"{tag}**{c['card_name']}** [{c['rarity']}] OVR:{c['ovr']}{mods}")
                embed = discord.Embed(
                    title=f"🎴 {interaction.user.display_name}'s Cards ({len(self.cards)})",
                    description="\n".join(lines),
                    color=0x00FF00,
                )
                embed.set_footer(text=f"Page {self.page}/{self.total_pages}")
                return embed

            @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
            async def prev_page(self, i: discord.Interaction, b: discord.ui.Button):
                if i.user.id != self.user_id:
                    await i.response.send_message("❌ Not your list.", ephemeral=True)
                    return
                self.page = max(1, self.page - 1)
                self.update_buttons()
                await i.response.edit_message(embed=self.build_embed(), view=self)

            @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
            async def next_page(self, i: discord.Interaction, b: discord.ui.Button):
                if i.user.id != self.user_id:
                    await i.response.send_message("❌ Not your list.", ephemeral=True)
                    return
                self.page = min(self.total_pages, self.page + 1)
                self.update_buttons()
                await i.response.edit_message(embed=self.build_embed(), view=self)

            def update_buttons(self):
                self.children[0].disabled = self.page == 1
                self.children[1].disabled = self.page == self.total_pages

            async def on_timeout(self):
                try:
                    for item in self.children:
                        item.disabled = True
                    await self.message.edit(view=self)
                except:
                    pass

        view = CardListPaginator(cards, interaction.user.id)
        view.update_buttons()
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()

    @bot.tree.command(name="card_completion", description="Show card completion for a player", guild=guild)
    @app_commands.describe(player="Player to check")
    async def card_completion(interaction: discord.Interaction, player: discord.User = None):
        target = player or interaction.user
        data = get_completion(target.id)
        if not data:
            await interaction.response.send_message(f"{target.mention} has no cards.", ephemeral=True)
            return

        total_templates = len(get_all_templates())
        owned = sum(1 for d in data if d["total"] > 0)

        class CompletionPaginator(discord.ui.View):
            def __init__(self, data, owned, total):
                super().__init__(timeout=120)
                self.data = data
                self.owned = owned
                self.total = total
                self.per_page = 10
                self.total_pages = max(1, (len(data) + self.per_page - 1) // self.per_page)
                self.page = 1
                self.message = None

            def build_embed(self):
                start = (self.page - 1) * self.per_page
                page_data = self.data[start:start + self.per_page]
                lines = []
                for d in page_data:
                    owned_str = "✅" if d["total"] > 0 else "❌"
                    extra = ""
                    if d["shiny_count"]:
                        extra += f" ✨x{d['shiny_count']}"
                    if d["mythical_count"]:
                        extra += f" 🌌x{d['mythical_count']}"
                    lines.append(f"{owned_str} **{d['name']}** [{d['rarity']}] — {d['total']} owned{extra}")
                embed = discord.Embed(
                    title=f"📋 {target.display_name}'s Completion ({self.owned}/{self.total})",
                    description="\n".join(lines),
                    color=0x00BFFF,
                )
                embed.set_footer(text=f"Page {self.page}/{self.total_pages}")
                return embed

            @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
            async def prev_page(self_, i: discord.Interaction, b: discord.ui.Button):
                if i.user.id != interaction.user.id and not is_admin(i):
                    await i.response.send_message("❌ Not your list.", ephemeral=True)
                    return
                self_.page = max(1, self_.page - 1)
                self_.update_buttons()
                await i.response.edit_message(embed=self_.build_embed(), view=self_)

            @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
            async def next_page(self_, i: discord.Interaction, b: discord.ui.Button):
                if i.user.id != interaction.user.id and not is_admin(i):
                    await i.response.send_message("❌ Not your list.", ephemeral=True)
                    return
                self_.page = min(self_.total_pages, self_.page + 1)
                self_.update_buttons()
                await i.response.edit_message(embed=self_.build_embed(), view=self_)

            def update_buttons(self_):
                self_.children[0].disabled = self_.page == 1
                self_.children[1].disabled = self_.page == self_.total_pages

            async def on_timeout(self_):
                try:
                    for item in self_.children:
                        item.disabled = True
                    await self_.message.edit(view=self_)
                except:
                    pass

        view = CompletionPaginator(data, owned, total_templates)
        view.update_buttons()
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()

    @bot.tree.command(name="collection", description="Show missing cards", guild=guild)
    async def collection(interaction: discord.Interaction):
        owned = get_owned_template_ids(interaction.user.id)
        all_templates = get_all_templates()
        missing = [t for t in all_templates if t["id"] not in owned]
        if not missing:
            await interaction.response.send_message("🎉 You have all available cards!", ephemeral=True)
            return
        names = "\n".join(f"❌ **{t['name']}**" for t in missing[:30])
        embed = discord.Embed(
            title=f"📋 Missing Cards ({len(missing)}/{len(all_templates)})",
            description=names,
            color=0xFF0000,
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="battle", description="Battle another player's cards!", guild=guild)
    @app_commands.describe(player="Opponent")
    async def battle(interaction: discord.Interaction, player: discord.User):
        if player.id == interaction.user.id:
            await interaction.response.send_message("❌ You can't battle yourself!", ephemeral=True)
            return
        p1_cards = get_player_cards(interaction.user.id)
        p2_cards = get_player_cards(player.id)
        if len(p1_cards) < 3:
            await interaction.response.send_message("❌ You need at least 3 cards to battle!", ephemeral=True)
            return
        if len(p2_cards) < 3:
            await interaction.response.send_message("❌ Opponent needs at least 3 cards!", ephemeral=True)
            return

        battle_id = create_battle(interaction.user.id, player.id)
        await interaction.response.send_message(f"⚔️ Battle started against {player.mention}! Check your DMs.", ephemeral=True)
        guild = interaction.guild
        await run_battle(bot, battle_id, interaction.user, player, guild)

    @bot.tree.command(name="redeem", description="[ADMIN] Create a card for a player", guild=guild)
    @app_commands.describe(name="Card template name", player="Recipient", attack="ATK stat", speed="SPD stat", health="HP stat", shiny="Is shiny", mythical="Is mythical")
    async def redeem(interaction: discord.Interaction, name: str, player: discord.User, attack: int, speed: int, health: int, shiny: bool = False, mythical: bool = False):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return

        templates = [t for t in get_all_templates() if t["name"].lower() == name.lower()]
        if not templates:
            add_card_template(name, health=health, attack=attack, speed=speed, rarity="F")
            templates = [t for t in get_all_templates() if t["name"].lower() == name.lower()]
        template = templates[0]

        from bot.cards.models import RARITY_COLORS
        rarity = template["rarity"]
        ovr = 2 * attack + health + speed

        cid = insert_card_instance(
            owner_id=player.id,
            template_id=template["id"],
            health=health,
            attack=attack,
            speed=speed,
            h_mod=0,
            a_mod=0,
            s_mod=0,
            is_shiny=shiny,
            is_mythical=mythical,
            rarity=rarity,
            ovr=ovr,
            is_special=template.get("is_special", False),
        )
        await interaction.response.send_message(f"✅ Redeemed **{name}** for {player.mention}! (ID: {cid})", ephemeral=True)

    @bot.tree.command(name="give", description="[ADMIN] Give any card to a player (random modifiers unless overridden)", guild=guild)
    @app_commands.describe(player="Recipient", card_name="Template name", shiny="Override shiny", mythical="Override mythical", hp_mod="HP modifier (-0.15 to 0.15)", atk_mod="ATK modifier", spd_mod="SPD modifier")
    async def give_card(interaction: discord.Interaction, player: discord.User, card_name: str, shiny: Optional[bool] = None, mythical: Optional[bool] = None, hp_mod: Optional[float] = None, atk_mod: Optional[float] = None, spd_mod: Optional[float] = None):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        templates = [t for t in get_all_templates() if t["name"].lower().strip() == card_name.lower().strip()]
        if not templates:
            await interaction.response.send_message("❌ No template found with that name.", ephemeral=True)
            return
        template = templates[0]
        card = generate_card(template, from_mafia=False)
        if shiny is not None:
            card["is_shiny"] = shiny
        if mythical is not None:
            card["is_mythical"] = mythical
        if hp_mod is not None:
            card["health_mod"] = round(hp_mod, 4)
        if atk_mod is not None:
            card["attack_mod"] = round(atk_mod, 4)
        if spd_mod is not None:
            card["speed_mod"] = round(spd_mod, 4)

        card["health"], card["attack"], card["speed"] = apply_modifiers(
            template["health"], template["attack"], template["speed"],
            card["health_mod"], card["attack_mod"], card["speed_mod"],
        )
        card["ovr"] = compute_ovr(card["health"], card["attack"], card["speed"])

        cid = insert_card_instance(
            owner_id=player.id,
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
        shiny_s = " ✨" if card["is_shiny"] else ""
        mythical_s = " 🌌" if card["is_mythical"] else ""
        await interaction.response.send_message(f"✅ Gave **{template['name']}**{shiny_s}{mythical_s} [{card['rarity']}] OVR:{card['ovr']} to {player.mention}! (ID: {cid})", ephemeral=True)

    @bot.tree.command(name="spawn", description="[ADMIN] Spawn a wild card with optional overrides", guild=guild)
    @app_commands.describe(card_name="Template name", channel="Override spawn channel", shiny="Force shiny", mythical="Force mythical", hp_mod="HP modifier (-0.15 to 0.15)", atk_mod="ATK modifier", spd_mod="SPD modifier")
    @app_commands.autocomplete(card_name=template_autocomplete)
    async def spawn_card(interaction: discord.Interaction, card_name: str, channel: discord.TextChannel = None, shiny: Optional[bool] = None, mythical: Optional[bool] = None, hp_mod: Optional[float] = None, atk_mod: Optional[float] = None, spd_mod: Optional[float] = None):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return

        templates = [t for t in get_all_templates() if t["name"].lower().strip() == card_name.lower().strip()]
        if not templates:
            await interaction.response.send_message("❌ No template found with that name.", ephemeral=True)
            return
        template = templates[0]

        card = generate_card(template, from_mafia=False)
        if shiny is not None:
            card["is_shiny"] = shiny
        if mythical is not None:
            card["is_mythical"] = mythical
        if hp_mod is not None:
            card["health_mod"] = round(hp_mod, 4)
        if atk_mod is not None:
            card["attack_mod"] = round(atk_mod, 4)
        if spd_mod is not None:
            card["speed_mod"] = round(spd_mod, 4)

        card["health"], card["attack"], card["speed"] = apply_modifiers(
            template["health"], template["attack"], template["speed"],
            card["health_mod"], card["attack_mod"], card["speed_mod"],
        )
        card["ovr"] = compute_ovr(card["health"], card["attack"], card["speed"])

        from bot.database.db import get_config
        spawn_channel_id = get_config("card_spawn_channel")
        spawn_channel = channel or (bot.get_channel(int(spawn_channel_id)) if spawn_channel_id else None)
        if not spawn_channel:
            await interaction.response.send_message("❌ No spawn channel configured. Use /set_spawn first or specify a channel.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🌟 A wild card appeared!",
            description=f"**{template['name']}**\n\nFirst to catch it gets the card!",
            color=0x00FF00,
        )
        if template.get("image_url"):
            embed.set_image(url=template["image_url"])

        view = CatchView(template, bot)
        view.override_card = card
        msg = await spawn_channel.send(embed=embed, view=view)
        view.message = msg

        await interaction.response.send_message(f"✅ Spawned **{template['name']}** in {spawn_channel.mention}!", ephemeral=True)

        import asyncio
        await asyncio.sleep(CATCH_TIMEOUT)
        if not view.caught:
            for item in view.children:
                item.disabled = True
            await msg.edit(content="⏰ The card got away...", view=view)

    @bot.tree.command(name="card_add_template", description="[ADMIN] Add a new card template", guild=guild)
    @app_commands.describe(name="Person's name", health="Base HP (max 5000)", attack="Base ATK (max 3000)", speed="Base SPD (max 1000)", image_url="Spawn encounter image URL", catch_image_url="Base card art URL", shiny_catch_image_url="Shiny card art URL", mythical_catch_image_url="Mythical card art URL")
    async def card_add_template_cmd(interaction: discord.Interaction, name: str, health: int = 1000, attack: int = 500, speed: int = 200, image_url: str = "", catch_image_url: str = "", shiny_catch_image_url: str = "", mythical_catch_image_url: str = ""):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        existing = [t for t in get_all_templates() if t["name"].lower() == name.lower()]
        if existing:
            await interaction.response.send_message("❌ Template already exists.", ephemeral=True)
            return
        ovr = compute_ovr(health, attack, speed)
        rarity = compute_rarity(ovr)
        add_card_template(name, health, attack, speed, rarity, image_url, catch_image_url, shiny_catch_image_url, mythical_catch_image_url, quote="")
        await interaction.response.send_message(f"✅ Added card template: **{name}** [{rarity}] OVR:{ovr} HP:{health} ATK:{attack} SPD:{speed}", ephemeral=True)

    @bot.tree.command(name="card_add_special_template", description="[ADMIN] Add a special card template", guild=guild)
    @app_commands.describe(name="Card name", health="Base HP", attack="Base ATK", speed="Base SPD", image_url="Spawn image URL", catch_image_url="Card art URL")
    async def card_add_special_template_cmd(interaction: discord.Interaction, name: str, health: int = 1000, attack: int = 500, speed: int = 200, image_url: str = "", catch_image_url: str = ""):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        existing = [t for t in get_all_templates() if t["name"].lower() == name.lower()]
        if existing:
            await interaction.response.send_message("❌ Template already exists.", ephemeral=True)
            return
        ovr = compute_ovr(health, attack, speed)
        rarity = compute_rarity(ovr)
        add_card_template(name, health, attack, speed, rarity, image_url, catch_image_url, is_special=True)
        await interaction.response.send_message(f"✅ Added SPECIAL template: **{name}** [{rarity}] OVR:{ovr}", ephemeral=True)

    @bot.tree.command(name="special_spawn_toggle", description="[ADMIN] Toggle spawning of special cards", guild=guild)
    async def special_spawn_toggle(interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        from bot.database.db import get_config, set_config
        current = get_config("special_spawn_enabled")
        if current == "1":
            set_config("special_spawn_enabled", "0")
            await interaction.response.send_message("❌ Special card spawning disabled.", ephemeral=True)
        else:
            set_config("special_spawn_enabled", "1")
            await interaction.response.send_message("✅ Special card spawning enabled.", ephemeral=True)

    @bot.tree.command(name="card_delete_template", description="[ADMIN] Delete a card template", guild=guild)
    @app_commands.describe(name="Template name to delete")
    @app_commands.autocomplete(name=template_autocomplete)
    async def card_delete_template_cmd(interaction: discord.Interaction, name: str):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        deleted = delete_card_template(name)
        if deleted:
            await interaction.response.send_message(f"✅ Deleted template: **{name}**", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ No template found with that name.", ephemeral=True)

    @bot.tree.command(name="set_spawn", description="[ADMIN] Set the card spawn channel", guild=guild)
    @app_commands.describe(channel="Channel to spawn cards in")
    async def set_spawn(interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        from bot.database.db import set_config
        set_config("card_spawn_channel", str(channel.id))
        set_config("card_spawn_enabled", "1")
        await interaction.response.send_message(f"✅ Cards will spawn in {channel.mention}.", ephemeral=True)
        spawner = getattr(bot, 'card_spawner', None)
        if spawner:
            spawner.spawn_channel_id = channel.id
            await spawner.start()

    @bot.tree.command(name="card_debug", description="[ADMIN] Show card DB diagnostics", guild=guild)
    async def card_debug(interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        from bot.cards.db import get_all_templates
        from bot.database.db import get_config, USE_PG, Connection
        from bot.database.driver import q
        templates = get_all_templates()
        spawn_channel = get_config("card_spawn_channel")
        msg = (
            f"**Database:** {'PostgreSQL' if USE_PG else 'SQLite'}\n"
            f"**Templates:** {len(templates)}\n"
            f"**Spawn channel:** {spawn_channel or 'Not set'}\n"
        )
        if templates:
            msg += "**Template names:** " + ", ".join(t["name"] for t in templates[:10]) + "\n"
        try:
            conn = Connection()
            cur = conn.execute("SELECT COUNT(*) FROM points")
            row = cur.fetchone()
            conn.close()
            count = row[0] if row else 0
            msg += f"**Points records:** {count}\n"
        except Exception as e:
            msg += f"**Points DB error:** {e}\n"
        await interaction.response.send_message(msg, ephemeral=True)

    @bot.tree.command(name="card_spawn_stop", description="[ADMIN] Stop card spawning", guild=guild)
    async def card_spawn_stop(interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        from bot.database.db import set_config
        set_config("card_spawn_enabled", "0")
        spawner = getattr(bot, 'card_spawner', None)
        if spawner:
            spawner._task = None
        await interaction.response.send_message("✅ Card spawns stopped.", ephemeral=True)

    @bot.tree.command(name="card_spawn_start", description="[ADMIN] Start card spawning", guild=guild)
    async def card_spawn_start(interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        from bot.database.db import set_config
        set_config("card_spawn_enabled", "1")
        spawner = getattr(bot, 'card_spawner', None)
        if spawner and not spawner._task:
            await spawner.start()
        await interaction.response.send_message("✅ Card spawns started.", ephemeral=True)

    @bot.tree.command(name="boss_battle", description="[ADMIN] Start a boss battle with a card", guild=guild)
    @app_commands.describe(card_name="Template name to fight as boss")
    @app_commands.autocomplete(card_name=template_autocomplete)
    async def boss_battle(interaction: discord.Interaction, card_name: str):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        templates = [t for t in get_all_templates() if t["name"].lower().strip() == card_name.lower().strip()]
        if not templates:
            await interaction.response.send_message("❌ No template found with that name.", ephemeral=True)
            return
        from bot.cards.boss_battle import BossBattle
        bb = BossBattle(bot, interaction.channel, templates[0], interaction.user)
        await interaction.response.send_message("👹 Boss battle starting...", ephemeral=True)

        async def run_boss_battle():
            try:
                await bb.run()
            except Exception as e:
                print(f"Boss battle error: {e}", flush=True)
                import traceback
                traceback.print_exc()

        asyncio.create_task(run_boss_battle())

    @bot.tree.command(name="auction", description="[ADMIN] Start a card auction", guild=guild)
    @app_commands.describe(card_id="Card ID to auction", min_bid="Minimum starting bid", instant_bid="Bid that instantly wins", duration="Auction duration in minutes")
    @app_commands.autocomplete(card_id=card_autocomplete)
    async def auction(interaction: discord.Interaction, card_id: str, min_bid: int, instant_bid: int, duration: int):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        card = get_card_instance(int(card_id))
        if not card:
            await interaction.response.send_message("❌ Card not found.", ephemeral=True)
            return

        mods = []
        if card["health_mod"]: mods.append(f"HP{card['health_mod']*100:+.0f}%")
        if card["attack_mod"]: mods.append(f"ATK{card['attack_mod']*100:+.0f}%")
        if card["speed_mod"]: mods.append(f"SPD{card['speed_mod']*100:+.0f}%")
        mod_str = f" ({', '.join(mods)})" if mods else ""
        description = (
            f"{'✨' if card['is_shiny'] else ''}{'🌌' if card['is_mythical'] else ''}"
            f"**{card['card_name']}** [{card['rarity']}] OVR:{card['ovr']}{mod_str}\n\n"
            f"**Minimum bid:** {min_bid} points\n"
            f"**Instant win:** {instant_bid} points\n"
            f"**Time left:** {duration} minutes\n"
            f"**Highest bid:** None"
        )

        embed = discord.Embed(title=f"🏆 Auction: {card['card_name']}", description=description, color=0xFFD700)
        img = ""
        if card["is_mythical"]: img = card.get("mythical_catch_image_url") or ""
        if not img and card["is_shiny"]: img = card.get("shiny_catch_image_url") or ""
        if not img: img = card.get("catch_image_url") or ""
        if img: embed.set_image(url=img)

        card_id_val = int(card_id)
        transfer_card(card_id_val, interaction.user.id)

        class AuctionView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=duration * 60)
                self.highest_bidder = None
                self.highest_amount = 0
                self.embed = embed
                self.message = None

            async def refresh_embed(self):
                lines = description.split("\n")
                bid_line = f"**Highest bid:** {self.highest_amount} by <@{self.highest_bidder}>" if self.highest_bidder else "**Highest bid:** None"
                new_desc = "\n".join(lines[:-1]) + "\n" + bid_line
                self.embed.description = new_desc
                if self.message:
                    await self.message.edit(embed=self.embed)

            @discord.ui.button(label="💰 Bid", style=discord.ButtonStyle.success, emoji="💰")
            async def bid_button(self_, i: discord.Interaction, b: discord.ui.Button):
                if self_.highest_bidder == i.user.id:
                    await i.response.send_message("❌ You already have the highest bid!", ephemeral=True)
                    return

                class BidModal(discord.ui.Modal, title="Place your bid"):
                    bid_amount = discord.ui.TextInput(label=f"Bid (min {min_bid})", style=discord.TextStyle.short)

                    async def on_submit(self, modal_i: discord.Interaction):
                        try:
                            amount = int(self.bid_amount.value)
                        except ValueError:
                            await modal_i.response.send_message("❌ Must be a whole number.", ephemeral=True)
                            return
                        if amount <= self_.highest_amount:
                            await modal_i.response.send_message(f"❌ Bid must be higher than {self_.highest_amount}.", ephemeral=True)
                            return
                        if amount < min_bid:
                            await modal_i.response.send_message(f"❌ Minimum bid is {min_bid}.", ephemeral=True)
                            return

                        from bot.database.db import get_points, deduct_points
                        balance = get_points(i.user.id)["points"]
                        if amount > balance:
                            await modal_i.response.send_message(f"❌ You only have {balance} points.", ephemeral=True)
                            return

                        if self_.highest_bidder:
                            deduct_points(self_.highest_bidder, -self_.highest_amount)

                        deduct_points(i.user.id, amount)
                        self_.highest_bidder = i.user.id
                        self_.highest_amount = amount
                        await self_.refresh_embed()
                        await modal_i.response.send_message(f"✅ Bid of {amount} placed!", ephemeral=True)

                        if amount >= instant_bid:
                            await self_.end_auction()

                await i.response.send_modal(BidModal())

            async def end_auction(self_):
                for item in self_.children:
                    item.disabled = True
                if self_.highest_bidder:
                    transfer_card(card_id_val, self_.highest_bidder)
                    user = bot.get_user(self_.highest_bidder)
                    mention = user.mention if user else f"<@{self_.highest_bidder}>"
                    self_.embed.description += f"\n\n🏆 **Winner:** {mention} for {self_.highest_amount} points!"
                else:
                    self_.embed.description += "\n\n❌ No bids — card returned."
                await self_.message.edit(embed=self_.embed, view=self_)
                self_.stop()

            @discord.ui.button(label="Cancel Auction", style=discord.ButtonStyle.danger, emoji="⛔")
            async def cancel_auction(self_, i: discord.Interaction, b: discord.ui.Button):
                if i.user.id != ADMIN_USER_ID and not is_admin(i):
                    await i.response.send_message("❌ Only the admin can cancel.", ephemeral=True)
                    return
                if self_.highest_bidder:
                    deduct_points(self_.highest_bidder, -self_.highest_amount)
                for item in self_.children:
                    item.disabled = True
                self_.embed.description += "\n\n⛔ Auction cancelled by admin."
                await self_.message.edit(embed=self_.embed, view=self_)
                self_.stop()
                await i.response.send_message("✅ Auction cancelled.", ephemeral=True)

            async def on_timeout(self_):
                await self_.end_auction()

        view = AuctionView()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

