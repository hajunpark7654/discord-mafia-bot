import random

RARITY_COLORS = {
    "S": 0xFFFFFF,
    "A": 0x87CEEB,
    "B": 0x0000CD,
    "C": 0x800080,
    "D": 0xFF0000,
    "F": 0xFFA500,
}


def compute_ovr(health, attack, speed):
    return 2 * attack + health + speed


def compute_rarity(ovr):
    if ovr >= 11000:
        return "S"
    elif ovr >= 9000:
        return "A"
    elif ovr >= 7000:
        return "B"
    elif ovr >= 5000:
        return "C"
    elif ovr >= 3000:
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


CATCH_SHINY_CHANCE = 0.05
CATCH_MYTHICAL_CHANCE = 0.0005
MAFIA_SHINY_CHANCE = 0.20
MAFIA_MYTHICAL_CHANCE = 0.01


def generate_card(template, from_mafia=False):
    health = template["health"]
    attack = template["attack"]
    speed = template["speed"]
    rarity = template["rarity"]
    is_special = template.get("is_special", False)

    if is_special:
        h_mod = a_mod = s_mod = 0.0
        is_shiny = False
        is_mythical = False
    elif from_mafia:
        h_mod = a_mod = s_mod = 0.0
        is_shiny = random.random() < MAFIA_SHINY_CHANCE
        is_mythical = random.random() < MAFIA_MYTHICAL_CHANCE
        # Guarantee B tier or higher by bumping stats if needed
        min_ovr = 7000
        if compute_ovr(health, attack, speed) < min_ovr:
            scale = min_ovr / compute_ovr(health, attack, speed)
            health = max(1, round(health * scale))
            attack = max(1, round(attack * scale))
            speed = max(1, round(speed * scale))
            rarity = compute_rarity(compute_ovr(health, attack, speed))
    else:
        h_mod = roll_modifier()
        a_mod = roll_modifier()
        s_mod = roll_modifier()
        is_shiny = random.random() < CATCH_SHINY_CHANCE
        is_mythical = random.random() < CATCH_MYTHICAL_CHANCE

    f_health, f_attack, f_speed = apply_modifiers(health, attack, speed, h_mod, a_mod, s_mod)
    ovr = compute_ovr(f_health, f_attack, f_speed)

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
        "is_special": is_special,
        "rarity": rarity,
        "ovr": ovr,
    }
