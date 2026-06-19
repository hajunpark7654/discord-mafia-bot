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
    return [
        app_commands.Choice(name=f"#{c['id']} {c['card_name']} [{c['rarity']}]", value=str(c["id"]))
        for c in cards if current.lower() in c["card_name"].lower() or current.isdigit() and str(c["id"]).startswith(current)
    ][:25]


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
        img = card.get("image_url") or ""
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
    @app_commands.describe(sort="Sort by (rarity, shiny, mythical)", page="Page number")
    async def card_list(interaction: discord.Interaction, sort: str = None, page: int = 1):
        cards = get_player_cards(interaction.user.id)
        if not cards:
            await interaction.response.send_message("You don't have any cards yet!", ephemeral=True)
            return

        if sort == "shiny":
            cards = [c for c in cards if c["is_shiny"]] + [c for c in cards if not c["is_shiny"]]
        elif sort == "mythical":
            cards = [c for c in cards if c["is_mythical"]] + [c for c in cards if not c["is_mythical"]]

        per_page = 30
        total_pages = max(1, (len(cards) + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        page_cards = cards[start:start + per_page]

        lines = []
        for c in page_cards:
            tag = ""
            if c["is_shiny"]:
                tag += "✨"
            if c["is_mythical"]:
                tag += "🌌"
            mods = ""
            parts = []
            if c["health_mod"]: parts.append(f"HP{c['health_mod']*100:+.0f}%")
            if c["attack_mod"]: parts.append(f"ATK{c['attack_mod']*100:+.0f}%")
            if c["speed_mod"]: parts.append(f"SPD{c['speed_mod']*100:+.0f}%")
            if parts: mods = f" ({', '.join(parts)})"
            lines.append(f"`#{c['id']}` {tag}**{c['card_name']}** [{c['rarity']}] OVR:{c['ovr']}{mods}")

        embed = discord.Embed(
            title=f"🎴 {interaction.user.display_name}'s Cards ({len(cards)})",
            description="\n".join(lines),
            color=0x00FF00,
        )
        embed.set_footer(text=f"Page {page}/{total_pages}")
        await interaction.response.send_message(embed=embed)

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
        lines = []
        for d in data:
            owned_str = "✅" if d["total"] > 0 else "❌"
            extra = ""
            if d["shiny_count"]:
                extra += f" ✨x{d['shiny_count']}"
            if d["mythical_count"]:
                extra += f" 🌌x{d['mythical_count']}"
            lines.append(f"{owned_str} **{d['name']}** — {d['total']} owned{extra}")

        embed = discord.Embed(
            title=f"📋 {target.display_name}'s Completion ({owned}/{total_templates})",
            description="\n".join(lines[:25]),
            color=0x00BFFF,
        )
        await interaction.response.send_message(embed=embed)

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
        )
        await interaction.response.send_message(f"✅ Redeemed **{name}** for {player.mention}! (ID: {cid})", ephemeral=True)

    @bot.tree.command(name="give", description="[ADMIN] Give any card to a player (random modifiers unless overridden)", guild=guild)
    @app_commands.describe(player="Recipient", card_name="Template name", shiny="Override shiny", mythical="Override mythical", hp_mod="HP modifier (-0.15 to 0.15)", atk_mod="ATK modifier", spd_mod="SPD modifier")
    async def give_card(interaction: discord.Interaction, player: discord.User, card_name: str, shiny: Optional[bool] = None, mythical: Optional[bool] = None, hp_mod: Optional[float] = None, atk_mod: Optional[float] = None, spd_mod: Optional[float] = None):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        templates = [t for t in get_all_templates() if t["name"].lower() == card_name.lower()]
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
        )
        shiny_s = " ✨" if card["is_shiny"] else ""
        mythical_s = " 🌌" if card["is_mythical"] else ""
        await interaction.response.send_message(f"✅ Gave **{template['name']}**{shiny_s}{mythical_s} [{card['rarity']}] OVR:{card['ovr']} to {player.mention}! (ID: {cid})", ephemeral=True)

    @bot.tree.command(name="spawn", description="[ADMIN] Spawn a wild card (first clicker catches it)", guild=guild)
    @app_commands.describe(card_name="Template name", channel="Override spawn channel (defaults to /set_spawn)")
    async def spawn_card(interaction: discord.Interaction, card_name: str, channel: discord.TextChannel = None):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return

        templates = [t for t in get_all_templates() if t["name"].lower() == card_name.lower()]
        if not templates:
            await interaction.response.send_message("❌ No template found with that name.", ephemeral=True)
            return
        template = templates[0]

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
        if template.get("catch_image_url"):
            embed.set_image(url=template["catch_image_url"])

        view = CatchView(template, bot)
        msg = await spawn_channel.send(embed=embed, view=view)
        view.message = msg

        await interaction.response.send_message(f"✅ Spawned **{template['name']}** in {spawn_channel.mention}!", ephemeral=True)

        import asyncio
        await asyncio.sleep(CATCH_TIMEOUT)
        if not view.caught:
            view.disable_all_items()
            await msg.edit(content="⏰ The card got away...", view=view)

    @bot.tree.command(name="card_add_template", description="[ADMIN] Add a new card template", guild=guild)
    @app_commands.describe(name="Person's name", health="Base HP (max 5000)", attack="Base ATK (max 3000)", speed="Base SPD (max 1000)", image_url="Card image URL", catch_image_url="Spawn image URL", shiny_catch_image_url="Image for shiny spawn", mythical_catch_image_url="Image for mythical spawn")
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

    @bot.tree.command(name="card_delete_template", description="[ADMIN] Delete a card template", guild=guild)
    @app_commands.describe(name="Template name to delete")
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
        from bot.database.db import get_config
        templates = get_all_templates()
        spawn_channel = get_config("card_spawn_channel")
        msg = (
            f"**Templates:** {len(templates)}\n"
            f"**Spawn channel:** {spawn_channel or 'Not set'}\n"
        )
        if templates:
            msg += "**Template names:** " + ", ".join(t["name"] for t in templates[:10]) + "\n"
        await interaction.response.send_message(msg, ephemeral=True)

