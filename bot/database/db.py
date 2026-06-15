import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "mafia_bot.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS points (
            user_id INTEGER PRIMARY KEY,
            points INTEGER DEFAULT 0,
            games_played INTEGER DEFAULT 0,
            games_won INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS game_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            game_type TEXT,
            player_count INTEGER,
            winner_team TEXT,
            summary TEXT
        );
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        INSERT OR IGNORE INTO config (key, value) VALUES ('autohost_enabled', '1');
        INSERT OR IGNORE INTO config (key, value) VALUES ('last_auto_game', '0');
    """)
    conn.commit()
    conn.close()


def get_points(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT points, games_played, games_won FROM points WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"points": row[0], "games_played": row[1], "games_won": row[2]}
    return {"points": 0, "games_played": 0, "games_won": 0}


def add_points(user_id, amount):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO points (user_id, points) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET points = points + ?",
              (user_id, amount, amount))
    conn.commit()
    conn.close()


def deduct_points(user_id, amount):
    add_points(user_id, -amount)


def increment_games_played(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO points (user_id, games_played) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET games_played = games_played + 1",
              (user_id,))
    conn.commit()
    conn.close()


def increment_games_won(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO points (user_id, games_won) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET games_won = games_won + 1",
              (user_id,))
    conn.commit()
    conn.close()


def get_leaderboard(limit=10):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT user_id, points, games_played, games_won FROM points ORDER BY points DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_game(game_type, player_count, winner_team, summary_dict):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO game_logs (timestamp, game_type, player_count, winner_team, summary) VALUES (?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), game_type, player_count, winner_team, json.dumps(summary_dict))
    )
    conn.commit()
    conn.close()


def get_config(key):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM config WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def set_config(key, value):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


def wipe_all_points():
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM points")
    conn.commit()
    conn.close()


def get_top_player():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT user_id, points FROM points ORDER BY points DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row:
        return {"user_id": row[0], "points": row[1], "name": f"<@{row[0]}>"}
    return None
