"""Seed Dragon Ball card templates into the database.
OVR = 2*ATK + HP + SPD
S: OVR >= 9000  |  A: >= 7500  |  B: >= 6500  |  C: >= 5000  |  D: >= 4000  |  F: < 4000
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bot.cards.db import add_card_template

# (name, hp, atk, spd, rarity, is_special=False)

templates = [
    # === S TIER ===
    ("Whis",                 4200, 2400, 480, "S"),
    ("Beerus",               4000, 2400, 450, "S"),
    ("Zeno",                 4500, 2200, 500, "S"),
    ("Grand Priest",         4100, 2300, 470, "S"),
    ("Goku (Ultra Instinct)",3800, 2500, 490, "S"),
    ("Vegito Blue",          3700, 2450, 480, "S"),
    ("Gogeta SS4",           3700, 2450, 440, "S"),
    ("Jiren (Full Power)",   3700, 2450, 400, "S"),
    ("Broly (Legendary SS)", 4000, 2400, 300, "S"),
    ("Gohan Beast",          3700, 2450, 400, "S"),

    # === A TIER ===
    ("Goku SSB",             3200, 2200, 400, "A"),
    ("Vegeta SSB",           3300, 2150, 380, "A"),
    ("Hit",                  3000, 2100, 450, "A"),
    ("Goku Black",           3100, 2100, 370, "A"),
    ("Frieza (Golden)",      3200, 2050, 360, "A"),
    ("Toppo (GoD)",          3400, 2050, 300, "A"),
    ("Merged Zamasu",        3300, 2000, 320, "A"),
    ("Kefla SS2",            2900, 2100, 400, "A"),
    ("Super Buu",            3500, 1900, 320, "A"),
    ("Cell (Perfect)",       3200, 1950, 400, "A"),

    # === B TIER ===
    ("Goku SS3",             2800, 1850, 350, "B"),
    ("Vegeta SS2",           2900, 1800, 320, "B"),
    ("Piccolo (Potential Unleashed)", 3000, 1750, 300, "B"),
    ("Gohan SS2",            2700, 1800, 340, "B"),
    ("Android 17",           2900, 1700, 360, "B"),
    ("Frieza (Final Form)",  2800, 1700, 330, "B"),
    ("Majin Buu",            3200, 1600, 250, "B"),
    ("Trunks (Future)",      2700, 1650, 320, "B"),
    ("Android 18",           2600, 1650, 340, "B"),
    ("Pikkon",               2600, 1700, 320, "B"),

    # === C TIER ===
    ("Goku SS",              2500, 1500, 300, "C"),
    ("Vegeta SS",            2600, 1450, 280, "C"),
    ("Piccolo",              2700, 1350, 290, "C"),
    ("Gohan",                2400, 1400, 310, "C"),
    ("Krillin",              2200, 1300, 350, "C"),
    ("Tien",                 2300, 1300, 290, "C"),
    ("Roshi (Max Power)",    2100, 1350, 280, "C"),
    ("Yamcha",               2200, 1250, 300, "C"),
    ("Android 16",           2800, 1200, 200, "C"),
    ("Chiaotzu",             1800, 1200, 320, "C"),
    ("Android 19",           2400, 1150, 240, "C"),
    ("Android 20 (Dr. Gero)",2300, 1150, 250, "C"),

    # === D TIER ===
    ("Raditz",               2000, 1100, 250, "D"),
    ("Nappa",                2200, 1000, 200, "D"),
    ("Guldo",                1500,  950, 350, "D"),
    ("Recoome",              2100, 1000, 180, "D"),
    ("Burter",               1600,  950, 380, "D"),
    ("Jeice",                1800, 1000, 250, "D"),
    ("Captain Ginyu",        2000, 1000, 220, "D"),
    ("Zarbon",               1800,  950, 240, "D"),
    ("Dodoria",              1900,  950, 200, "D"),
    ("Saibaman",             1900,  950, 200, "D"),
    ("Appule",               1700,  900, 230, "D"),
    ("Shisami",              1600,  900, 220, "D"),

    # === F TIER ===
    ("Frieza Soldier",       1000,  600, 150, "F"),
    ("Farmer",                800,  400, 100, "F"),
    ("Monkey King",           900,  450, 120, "F"),
    ("Pilaf",                 700,  350, 150, "F"),
    ("Oolong",                600,  300, 200, "F"),
    ("Pu'ar",                 500,  250, 250, "F"),
    ("Bee",                   400,  150, 180, "F"),
    ("Bulla",                 500,  200, 200, "F"),
    ("Mr. Satan",             800,  300, 120, "F"),
    ("King Kai",              600,  250, 150, "F"),
    ("Korin",                 700,  200, 300, "F"),
    ("Yajirobe",              900,  400, 150, "F"),
]

# Special cards (is_special=True)
special_templates = [
    ("Senzu Bean",            500,  100,  50, "F", True),
    ("Dragon Radar",          300,   50, 100, "F", True),
    ("Fusion Earrings",       800,  200, 100, "D", True),
    ("Super Dragon Balls",   2000,  500, 200, "C", True),
    ("Z Sword",              1000,  600, 150, "D", True),
    ("Shenron",              4500,  100,  50, "C", True),
]

for name, hp, atk, spd, rarity in templates:
    add_card_template(name, hp, atk, spd, rarity)

for name, hp, atk, spd, rarity, special in special_templates:
    add_card_template(name, hp, atk, spd, rarity, is_special=special)

total = len(templates) + len(special_templates)
print(f"Seeded {total} card templates into the database!")
