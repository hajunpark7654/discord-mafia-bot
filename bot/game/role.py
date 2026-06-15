import random
from config import (
    ROLE_DISTRIBUTION, MAFIA_SUPPORT_POOL, SPECIAL_TOWN_POOL, NEUTRAL_POOL,
    ROLE_REGISTRY,
)


def assign_roles(player_count, players):
    roles = generate_role_list(player_count)
    random.shuffle(players)
    assignments = []
    for i, player in enumerate(players):
        role_name = roles[i]
        player.role = role_name
        assignments.append(player)

    mafia_team = [p for p in assignments if ROLE_REGISTRY[p.role]["team"] == "mafia"]

    return assignments, mafia_team


def generate_role_list(player_count):
    if player_count < 5:
        return []

    if player_count <= 10:
        dist = ROLE_DISTRIBUTION[player_count]
    else:
        dist = generate_distribution_for_large(player_count)

    roles = []
    roles.extend(["mafia"] * dist["mafia"])
    roles.extend(random.sample(MAFIA_SUPPORT_POOL, dist["mafia_support"]))
    roles.extend(random.sample(NEUTRAL_POOL, dist["neutral"]))
    roles.append("doctor")
    if dist["sheriff"] > 0:
        roles.append("sheriff")
    roles.extend(["town"] * dist["town"])
    roles.extend(random.sample(SPECIAL_TOWN_POOL, dist["special_town"]))

    random.shuffle(roles)
    return roles


def generate_distribution_for_large(count):
    mafia_count = max(2, round(count * 0.25))
    mafia_support = max(1, round(count * 0.1))
    neutral_count = max(1, round(count * 0.15))
    doctor = 1
    sheriff = 1
    special_town = random.choice([1, 2])
    town_count = count - mafia_count - mafia_support - neutral_count - doctor - sheriff - special_town
    town_count = max(0, town_count)

    return {
        "mafia": mafia_count,
        "mafia_support": mafia_support,
        "neutral": neutral_count,
        "doctor": doctor,
        "sheriff": sheriff,
        "town": town_count,
        "special_town": special_town,
    }


def get_role_team(role_name):
    info = ROLE_REGISTRY.get(role_name, {})
    return info.get("team", "town")


def is_killing_role(role_name):
    info = ROLE_REGISTRY.get(role_name, {})
    return info.get("killing", False)


def get_points_key(role_name):
    info = ROLE_REGISTRY.get(role_name, {})
    return info.get("points_key", "town_win")
