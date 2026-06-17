import discord
from discord import PermissionOverwrite, Permissions
from config import (
    GAME_CATEGORY_NAME, TOWN_SQUARE_CHANNEL, MAFIA_DEN_CHANNEL,
    DEAD_CHAT_CHANNEL, PLAYER_ROLE_NAME, DEAD_ROLE_NAME,
)


async def setup_game_channels(game, guild):
    overwrites_everyone = PermissionOverwrite(read_messages=False, send_messages=False)

    category = await guild.create_category(f"{GAME_CATEGORY_NAME} #{game.game_id}")
    game.game_category = category

    player_role = await guild.create_role(name=PLAYER_ROLE_NAME)
    game.player_role = player_role

    dead_role = await guild.create_role(name=DEAD_ROLE_NAME)
    game.dead_role = dead_role

    town_overwrites = {
        guild.default_role: overwrites_everyone,
        player_role: PermissionOverwrite(read_messages=True, send_messages=True),
        dead_role: PermissionOverwrite(read_messages=False, send_messages=False),
    }
    town_square = await category.create_text_channel(TOWN_SQUARE_CHANNEL, overwrites=town_overwrites)
    game.town_square = town_square

    den_overwrites = {
        guild.default_role: PermissionOverwrite(read_messages=False, send_messages=False),
        player_role: PermissionOverwrite(read_messages=False, send_messages=False),
        dead_role: PermissionOverwrite(read_messages=False, send_messages=False),
    }
    mafia_den = await category.create_text_channel(MAFIA_DEN_CHANNEL, overwrites=den_overwrites)
    game.mafia_den = mafia_den

    dead_overwrites = {
        guild.default_role: overwrites_everyone,
        dead_role: PermissionOverwrite(read_messages=True, send_messages=True),
    }
    dead_chat = await category.create_text_channel(DEAD_CHAT_CHANNEL, overwrites=dead_overwrites)
    game.dead_chat = dead_chat


async def add_mafia_permissions(game, guild, mafia_players):
    for player in mafia_players:
        member = guild.get_member(player.user_id)
        if member:
            await game.mafia_den.set_permissions(member, read_messages=True, send_messages=True)


async def remove_mafia_permissions(game, guild, mafia_players):
    for player in mafia_players:
        member = guild.get_member(player.user_id)
        if member:
            await game.mafia_den.set_permissions(member, overwrite=None)


async def toggle_mafia_chat(game, guild, open_chat):
    for player in game.players:
        if get_role_team(player.role) == "mafia" and player.alive:
            member = guild.get_member(player.user_id)
            if member:
                if open_chat:
                    await game.mafia_den.set_permissions(member, read_messages=True, send_messages=True)
                else:
                    await game.mafia_den.set_permissions(member, overwrite=None)


async def kill_player(game, guild, player):
    player.alive = False
    member = guild.get_member(player.user_id)
    if member:
        await member.remove_roles(game.player_role)
        await member.add_roles(game.dead_role)
        await game.town_square.set_permissions(member, overwrite=None)
        await game.dead_chat.set_permissions(member, read_messages=True, send_messages=True)


def get_role_team(role_name):
    from config import ROLE_REGISTRY
    info = ROLE_REGISTRY.get(role_name, {})
    return info.get("faction", "town")


async def add_medium_dead_access(game, guild, player):
    if not game.dead_chat:
        return
    member = guild.get_member(player.user_id)
    if member:
        try:
            await game.dead_chat.set_permissions(member, read_messages=True, send_messages=True)
        except:
            pass


async def remove_medium_dead_access(game, guild, player):
    if not game.dead_chat:
        return
    member = guild.get_member(player.user_id)
    if member:
        try:
            await game.dead_chat.set_permissions(member, overwrite=None)
        except:
            pass


async def cleanup_game_channels(game, guild):
    import asyncio

    for player in game.players:
        member = guild.get_member(player.user_id)
        if member:
            try:
                await member.remove_roles(game.player_role)
            except:
                pass
            try:
                await member.remove_roles(game.dead_role)
            except:
                pass
            if player.original_roles:
                roles_to_add = [guild.get_role(rid) for rid in player.original_roles if guild.get_role(rid)]
                for role in roles_to_add:
                    try:
                        await member.add_roles(role)
                    except:
                        pass

    if game.town_square:
        try:
            await game.town_square.delete()
        except:
            pass
    if game.mafia_den:
        try:
            await game.mafia_den.delete()
        except:
            pass
    if game.dead_chat:
        try:
            await game.dead_chat.delete()
        except:
            pass

    if game.player_role:
        try:
            await game.player_role.delete()
        except:
            pass
    if game.dead_role:
        try:
            await game.dead_role.delete()
        except:
            pass

    if game.game_category:
        try:
            await game.game_category.delete()
        except:
            pass
