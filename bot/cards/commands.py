import discord
from discord import app_commands
from discord.ext import commands
from config import GUILD_ID, ADMIN_USER_ID
from bot.client import is_admin
from bot.cards.db import (
    get_player_cards, get_card_instance, transfer_card,
    get_all_templates, get_completion, get_owned_template_ids,
    add_card_template, create_battle, insert_card_instance,
)
from bot.cards.models import generate_card, RARITY_COLORS, compute_ovr, compute_rarity
from bot.cards.battle import run_battle


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
        embed = discord.Embed(
            title=f"{'✨ ' if card['is_shiny'] else ''}{'🌌 ' if card['is_mythical'] else ''}{card['card_name']}",
            color=color,
        )
        if card.get("image_url"):
            embed.set_image(url=card["image_url"])
        embed.add_field(name="Rarity", value=card["rarity"], inline=True)
        embed.add_field(name="Health", value=f"{card['health']} ({card['health_mod']*100:+.1f}%)" if card["health_mod"] else str(card["health"]), inline=True)
        embed.add_field(name="Attack", value=f"{card['attack']} ({card['attack_mod']*100:+.1f}%)" if card["attack_mod"] else str(card["attack"]), inline=True)
        embed.add_field(name="Speed", value=f"{card['speed']} ({card['speed_mod']*100:+.1f}%)" if card["speed_mod"] else str(card["speed"]), inline=True)
        embed.add_field(name="OVR", value=card["ovr"], inline=True)
        embed.add_field(name="Shiny", value="Yes ✨" if card["is_shiny"] else "No", inline=True)
        embed.add_field(name="Mythical", value="Yes 🌌" if card["is_mythical"] else "No", inline=True)
        if card.get("quote"):
            embed.set_footer(text=card["quote"])
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

        lines = []
        for c in cards[:50]:
            shiny = "✨ " if c["is_shiny"] else ""
            mythical = "🌌 " if c["is_mythical"] else ""
            mods = ""
            parts = []
            if c["health_mod"]: parts.append(f"HP{c['health_mod']*100:+.0f}%")
            if c["attack_mod"]: parts.append(f"ATK{c['attack_mod']*100:+.0f}%")
            if c["speed_mod"]: parts.append(f"SPD{c['speed_mod']*100:+.0f}%")
            if parts: mods = f" ({', '.join(parts)})"
            lines.append(f"`#{c['id']}` {shiny}{mythical}**{c['card_name']}** [{c['rarity']}] OVR:{c['ovr']}{mods}")

        embed = discord.Embed(
            title=f"🎴 {interaction.user.display_name}'s Cards ({len(cards)})",
            description="\n".join(lines[:30]),
            color=0x00FF00,
        )
        if len(lines) > 30:
            embed.set_footer(text=f"... and {len(lines) - 30} more")
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

    @bot.tree.command(name="give", description="[ADMIN] Give any card to a player (random modifiers)", guild=guild)
    @app_commands.describe(player="Recipient", card_name="Template name (case-insensitive)")
    async def give_card(interaction: discord.Interaction, player: discord.User, card_name: str):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        templates = [t for t in get_all_templates() if t["name"].lower() == card_name.lower()]
        if not templates:
            await interaction.response.send_message("❌ No template found with that name.", ephemeral=True)
            return
        template = templates[0]
        card = generate_card(template, from_mafia=False)
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
        shiny = " ✨" if card["is_shiny"] else ""
        mythical = " 🌌" if card["is_mythical"] else ""
        await interaction.response.send_message(f"✅ Gave **{template['name']}**{shiny}{mythical} [{card['rarity']}] OVR:{card['ovr']} to {player.mention}! (ID: {cid})", ephemeral=True)

    @bot.tree.command(name="card_add_template", description="[ADMIN] Add a new card template", guild=guild)
    @app_commands.describe(name="Person's name", health="Base HP (max 5000)", attack="Base ATK (max 3000)", speed="Base SPD (max 1000)", quote="Random quote/myth", image_url="Card image URL", catch_image_url="Spawn image URL")
    async def card_add_template_cmd(interaction: discord.Interaction, name: str, health: int = 1000, attack: int = 500, speed: int = 200, quote: str = "", image_url: str = "", catch_image_url: str = ""):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only the admin.", ephemeral=True)
            return
        existing = [t for t in get_all_templates() if t["name"].lower() == name.lower()]
        if existing:
            await interaction.response.send_message("❌ Template already exists.", ephemeral=True)
            return
        ovr = compute_ovr(health, attack, speed)
        rarity = compute_rarity(ovr)
        add_card_template(name, health, attack, speed, rarity, image_url, catch_image_url, quote)
        await interaction.response.send_message(f"✅ Added card template: **{name}** [{rarity}] OVR:{ovr} HP:{health} ATK:{attack} SPD:{speed}", ephemeral=True)

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

