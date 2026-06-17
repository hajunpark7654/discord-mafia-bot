import random
from config import (
    ROLE_DISTRIBUTION, ROLE_REGISTRY,
    MAFIA_KILLING_POOL, MAFIA_KILLING_WEIGHTS,
    MAFIA_SUPPORT_POOL, MAFIA_SUPPORT_WEIGHTS,
    NEUTRAL_CHAOTIC_POOL, NEUTRAL_LAWFUL_POOL,
    TOWN_SUPPORT_POOL, TOWN_SUPPORT_WEIGHTS,
    FACTION_MAFIA,
)


def weighted_pick(pool, weights):
    return random.choices(pool, weights=weights, k=1)[0]


def pick_roles_unique(pool, weights, count):
    if count <= 0:
        return []
    pool_copy = list(pool)
    weights_copy = list(weights)
    chosen = []
    for _ in range(count):
        if not pool_copy:
            break
        role = random.choices(pool_copy, weights=weights_copy, k=1)[0]
        chosen.append(role)
        idx = pool_copy.index(role)
        pool_copy.pop(idx)
        weights_copy.pop(idx)
    return chosen


def assign_roles(player_count, players):
    forced = [p for p in players if hasattr(p, '_forced_role') and p._forced_role]
    free = [p for p in players if not hasattr(p, '_forced_role') or not p._forced_role]

    roles = generate_role_list(player_count)

    assignments = []
    for player in forced:
        forced_role = player._forced_role
        if forced_role in roles:
            roles.remove(forced_role)
        else:
            roles.pop()
        player.role = forced_role
        assignments.append(player)

    random.shuffle(free)
    for i, player in enumerate(free):
        role_name = roles[i]
        player.role = role_name
        assignments.append(player)

    mafia_team = [p for p in assignments if get_role_faction(p.role) == FACTION_MAFIA]

    return assignments, mafia_team


def generate_role_list(player_count, exclude=None):
    if exclude is None:
        exclude = []
    if player_count < 5:
        return []

    if player_count <= 10:
        dist = ROLE_DISTRIBUTION[player_count]
    else:
        dist = generate_distribution_for_large(player_count)

    roles = []

    if dist["mafia_killing"] > 0:
        pool = [r for r in MAFIA_KILLING_POOL if r not in exclude]
        weights = [MAFIA_KILLING_WEIGHTS[MAFIA_KILLING_POOL.index(r)] for r in pool]
        killing = pick_roles_unique(pool, weights, dist["mafia_killing"]) if pool else []
        roles.extend(killing)

    if dist["mafia_support"] > 0:
        pool = [r for r in MAFIA_SUPPORT_POOL if r not in exclude]
        weights = [MAFIA_SUPPORT_WEIGHTS[MAFIA_SUPPORT_POOL.index(r)] for r in pool]
        support = pick_roles_unique(pool, weights, dist["mafia_support"]) if pool else []
        roles.extend(support)

    if dist["neutral"] > 0:
        neutral_pool = NEUTRAL_CHAOTIC_POOL + NEUTRAL_LAWFUL_POOL
        avail = [r for r in neutral_pool if r not in exclude]
        if avail:
            neutral_chaos_count = dist["neutral"] // 2 + (1 if dist["neutral"] % 2 == 1 and random.random() < 0.5 else 0)
            neutral_lawful_count = dist["neutral"] - neutral_chaos_count
            chaotic_avail = [r for r in NEUTRAL_CHAOTIC_POOL if r in avail]
            lawful_avail = [r for r in NEUTRAL_LAWFUL_POOL if r in avail]
            neutral_roles = []
            if chaotic_avail:
                neutral_roles.extend(random.sample(chaotic_avail, min(neutral_chaos_count, len(chaotic_avail))))
            if lawful_avail:
                neutral_roles.extend(random.sample(lawful_avail, min(neutral_lawful_count, len(lawful_avail))))
            random.shuffle(neutral_roles)
            roles.extend(neutral_roles)

    if "doctor" not in exclude:
        roles.append("doctor")
    if dist["sheriff"] > 0 and "sheriff" not in exclude:
        roles.append("sheriff")

    roles.extend(["town"] * dist["town"])

    if dist["town_support"] > 0:
        pool = [r for r in TOWN_SUPPORT_POOL if r not in exclude]
        weights = [TOWN_SUPPORT_WEIGHTS[TOWN_SUPPORT_POOL.index(r)] for r in pool]
        ts = pick_roles_unique(pool, weights, dist["town_support"]) if pool else []
        roles.extend(ts)

    random.shuffle(roles)
    return roles


def generate_distribution_for_large(count):
    mafia_count = max(2, round(count * 0.25))
    mafia_support = max(1, round(count * 0.1))
    neutral_count = max(1, round(count * 0.15))
    doctor = 1
    sheriff = 1
    town_support = random.choice([1, 2])
    town_count = count - mafia_count - mafia_support - neutral_count - doctor - sheriff - town_support
    town_count = max(0, town_count)

    return {
        "mafia_killing": mafia_count,
        "mafia_support": mafia_support,
        "neutral": neutral_count,
        "doctor": doctor,
        "sheriff": sheriff,
        "town": town_count,
        "town_support": town_support,
    }


def get_role_faction(role_name):
    info = ROLE_REGISTRY.get(role_name, {})
    return info.get("faction", "town")


def get_role_team(role_name):
    info = ROLE_REGISTRY.get(role_name, {})
    return info.get("team", "town")


def is_killing_role(role_name):
    info = ROLE_REGISTRY.get(role_name, {})
    return info.get("killing", False)


def get_points_key(role_name):
    info = ROLE_REGISTRY.get(role_name, {})
    return info.get("points_key", "town_win")
