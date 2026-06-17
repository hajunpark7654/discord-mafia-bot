import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "mafia_bot.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_card_tables():
    conn = get_connection()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS card_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            image_url TEXT DEFAULT '',
            catch_image_url TEXT DEFAULT '',
            quote TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS card_instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            health INTEGER NOT NULL,
            attack INTEGER NOT NULL,
            speed INTEGER NOT NULL,
            health_mod REAL DEFAULT 0,
            attack_mod REAL DEFAULT 0,
            speed_mod REAL DEFAULT 0,
            is_shiny INTEGER DEFAULT 0,
            is_mythical INTEGER DEFAULT 0,
            rarity TEXT NOT NULL,
            ovr INTEGER DEFAULT 0,
            obtained_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (template_id) REFERENCES card_templates(id)
        );
        CREATE TABLE IF NOT EXISTS card_battles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player1_id INTEGER NOT NULL,
            player2_id INTEGER NOT NULL,
            winner_id INTEGER,
            status TEXT DEFAULT 'pending',
            started_at TEXT DEFAULT (datetime('now')),
            finished_at TEXT
        );
    """)
    conn.commit()
    conn.close()


def add_card_template(name, image_url="", catch_image_url="", quote=""):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO card_templates (name, image_url, catch_image_url, quote) VALUES (?, ?, ?, ?)",
              (name, image_url, catch_image_url, quote))
    conn.commit()
    conn.close()


def get_all_templates():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM card_templates")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_template(template_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM card_templates WHERE id = ?", (template_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_random_template():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM card_templates ORDER BY RANDOM() LIMIT 1")
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def insert_card_instance(owner_id, template_id, health, attack, speed, h_mod, a_mod, s_mod, is_shiny, is_mythical, rarity, ovr):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""INSERT INTO card_instances
        (owner_id, template_id, health, attack, speed, health_mod, attack_mod, speed_mod, is_shiny, is_mythical, rarity, ovr)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (owner_id, template_id, health, attack, speed, h_mod, a_mod, s_mod, 1 if is_shiny else 0, 1 if is_mythical else 0, rarity, ovr))
    conn.commit()
    card_id = c.lastrowid
    conn.close()
    return card_id


def get_player_cards(owner_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""SELECT ci.*, ct.name as card_name, ct.image_url, ct.quote
        FROM card_instances ci
        JOIN card_templates ct ON ci.template_id = ct.id
        WHERE ci.owner_id = ?
        ORDER BY
            CASE ci.rarity
                WHEN 'S' THEN 0 WHEN 'A' THEN 1 WHEN 'B' THEN 2
                WHEN 'C' THEN 3 WHEN 'D' THEN 4 WHEN 'F' THEN 5
            END,
            ci.ovr DESC""", (owner_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_card_instance(card_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""SELECT ci.*, ct.name as card_name, ct.image_url, ct.quote
        FROM card_instances ci
        JOIN card_templates ct ON ci.template_id = ct.id
        WHERE ci.id = ?""", (card_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def transfer_card(card_id, new_owner_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE card_instances SET owner_id = ? WHERE id = ?", (new_owner_id, card_id))
    conn.commit()
    conn.close()


def get_owned_template_ids(owner_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""SELECT DISTINCT ci.template_id FROM card_instances ci WHERE ci.owner_id = ?""", (owner_id,))
    rows = c.fetchall()
    conn.close()
    return set(r[0] for r in rows)


def get_completion(owner_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""SELECT ct.name, ct.id as template_id,
        COUNT(ci.id) as total,
        SUM(CASE WHEN ci.is_shiny = 1 THEN 1 ELSE 0 END) as shiny_count,
        SUM(CASE WHEN ci.is_mythical = 1 THEN 1 ELSE 0 END) as mythical_count
        FROM card_templates ct
        LEFT JOIN card_instances ci ON ci.template_id = ct.id AND ci.owner_id = ?
        GROUP BY ct.id ORDER BY ct.name""", (owner_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_battle(player1_id, player2_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO card_battles (player1_id, player2_id, status) VALUES (?, ?, 'pending')",
              (player1_id, player2_id))
    conn.commit()
    battle_id = c.lastrowid
    conn.close()
    return battle_id


def get_battle(battle_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM card_battles WHERE id = ?", (battle_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def finish_battle(battle_id, winner_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE card_battles SET status = 'finished', winner_id = ?, finished_at = datetime('now') WHERE id = ?",
              (winner_id, battle_id))
    conn.commit()
    conn.close()
