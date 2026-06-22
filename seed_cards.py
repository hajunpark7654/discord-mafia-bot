"""CLI entry point to seed card templates. Also auto-runs from main.py on first boot."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bot.cards.seed import seed_card_templates

seed_card_templates()
print("Card templates seeded!")
