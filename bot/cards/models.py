import random
import math

MAX_HEALTH = 5000
MAX_ATTACK = 3000
MAX_SPEED = 1000

RARITY_TIERS = ["S", "A", "B", "C", "D", "F"]
RARITY_CHANCES = {"S": 0.001, "A": 0.079, "B": 0.12, "C": 0.20, "D": 0.25, "F": 0.35}
SHINY_CHANCE = 0.01
MYTHICAL_CHANCE = 0.0001

RARITY_COLORS = {
    "S": 0xFFFFFF,
    "A": 0x87CEEB,
    "B": 0x0000CD,
    "C": 0x800080,
    "D": 0xFF0000,
    "F": 0xFFA500,
}

RARITY_STAT_RANGES = {
    "S": {"health": (4000, 5000), "attack": (2400, 3000), "speed": (800, 1000)},
    "A": {"health": (3000, 4000), "attack": (1800, 2400), "speed": (600, 800)},
    "B": {"health": (2000, 3000), "attack": (1200, 1800), "speed": (400, 600)},
    "C": {"health": (1500, 2500), "attack": (800, 1400), "speed": (300, 500)},
    "D": {"health": (1000, 2000), "attack": (400, 1000), "speed": (200, 400)},
    "F": {"health": (500, 1500), "attack": (100, 600), "speed": (50, 250)},
}

S_OVR_THRESHOLD = 11000
A_OVR_THRESHOLD = 9000
B_OVR_THRESHOLD = 7000
C_OVR_THRESHOLD = 5000
D_OVR_THRESHOLD = 3000


def roll_rarity():
    r = random.random()
    cumulative = 0
    for tier, chance in RARITY_CHANCES.items():
        cumulative += chance
        if r < cumulative:
            return tier
    return "F"


def roll_stats(rarity):
    ranges = RARITY_STAT_RANGES[rarity]
    health = random.randint(*ranges["health"])
    attack = random.randint(*ranges["attack"])
    speed = random.randint(*ranges["speed"])
    return health, attack, speed


def compute_ovr(health, attack, speed):
    return 2 * attack + health + speed


def ovr_to_rarity(ovr):
    if ovr >= S_OVR_THRESHOLD:
        return "S"
    if ovr >= A_OVR_THRESHOLD:
        return "A"
    if ovr >= B_OVR_THRESHOLD:
        return "B"
    if ovr >= C_OVR_THRESHOLD:
        return "C"
    if ovr >= D_OVR_THRESHOLD:
        return "D"
    return "F"


def roll_modifier():
    return round(random.uniform(-0.15, 0.15), 4)


def apply_modifiers(health, attack, speed, h_mod, a_mod, s_mod):
    return (
        max(1, round(health * (1 + h_mod))),
        max(1, round(attack * (1 + a_mod))),
        max(1, round(speed * (1 + s_mod))),
    )


def roll_shiny():
    return random.random() < SHINY_CHANCE


def roll_mythical():
    return random.random() < MYTHICAL_CHANCE


def generate_card(template, from_mafia=False):
    rarity = roll_rarity()
    health, attack, speed = roll_stats(rarity)
    if from_mafia:
        h_mod = a_mod = s_mod = 0.0
    else:
        h_mod = roll_modifier()
        a_mod = roll_modifier()
        s_mod = roll_modifier()

    f_health, f_attack, f_speed = apply_modifiers(health, attack, speed, h_mod, a_mod, s_mod)
    ovr = compute_ovr(f_health, f_attack, f_speed)
    final_rarity = ovr_to_rarity(ovr)

    is_shiny = roll_shiny() if not from_mafia else False
    is_mythical = roll_mythical() if not from_mafia else False

    return {
        "template_id": template["id"],
        "health": f_health,
        "attack": f_attack,
        "speed": f_speed,
        "health_mod": h_mod,
        "attack_mod": a_mod,
        "speed_mod": s_mod,
        "is_shiny": is_shiny,
        "is_mythical": is_mythical,
        "rarity": final_rarity,
        "ovr": ovr,
    }
