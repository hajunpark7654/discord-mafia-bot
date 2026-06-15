import random
import asyncio
from config import ROLE_EMOJIS


def get_role_emoji(role_name):
    return ROLE_EMOJIS.get(role_name, "❓")


def format_player_list(players):
    return ", ".join(p["mention"] for p in players)


def chunk_list(lst, size):
    return [lst[i:i + size] for i in range(0, len(lst), size)]


def random_interval(min_sec, max_sec):
    return random.randint(min_sec, max_sec)


def choose_multiple(pool, count):
    if count <= 0:
        return []
    return random.sample(pool, min(count, len(pool)))


async def await_with_force(seconds, force_attr, game):
    check_interval = 5
    elapsed = 0
    while elapsed < seconds:
        await asyncio.sleep(min(check_interval, seconds - elapsed))
        elapsed += check_interval
        if getattr(game, force_attr, False):
            setattr(game, force_attr, False)
            return True
    return False
