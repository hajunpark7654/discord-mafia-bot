import json
from datetime import datetime
from .driver import Connection, USE_PG, q


def init_db():
    conn = Connection()
    if USE_PG:
        conn.execute("CREATE TABLE IF NOT EXISTS points (user_id BIGINT PRIMARY KEY, points INTEGER DEFAULT 0, games_played INTEGER DEFAULT 0, games_won INTEGER DEFAULT 0)")
        conn.execute("CREATE TABLE IF NOT EXISTS game_logs (id SERIAL PRIMARY KEY, timestamp TEXT, game_type TEXT, player_count INTEGER, winner_team TEXT, summary TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO config (key, value) VALUES ('autohost_enabled', '1') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO config (key, value) VALUES ('last_auto_game', '0') ON CONFLICT DO NOTHING")
    else:
        conn.execute("CREATE TABLE IF NOT EXISTS points (user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0, games_played INTEGER DEFAULT 0, games_won INTEGER DEFAULT 0)")
        conn.execute("CREATE TABLE IF NOT EXISTS game_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, game_type TEXT, player_count INTEGER, winner_team TEXT, summary TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(q("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)"), ("autohost_enabled", "1"))
        conn.execute(q("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)"), ("last_auto_game", "0"))
    conn.commit()
    conn.close()


def get_points(user_id):
    try:
        conn = Connection()
        cur = conn.execute(q("SELECT points, games_played, games_won FROM points WHERE user_id = ?"), (user_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            return {"points": row[0], "games_played": row[1], "games_won": row[2]}
    except Exception as e:
        print(f"get_points error: {e}")
    return {"points": 0, "games_played": 0, "games_won": 0}


def add_points(user_id, amount):
    try:
        conn = Connection()
        conn.execute(q("INSERT INTO points (user_id, points) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET points = points + ?"),
                     (user_id, amount, amount))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"add_points error (user={user_id}, amount={amount}): {e}")
        import traceback
        traceback.print_exc()


def deduct_points(user_id, amount):
    add_points(user_id, -amount)


def increment_games_played(user_id):
    try:
        conn = Connection()
        conn.execute(q("INSERT INTO points (user_id, games_played) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET games_played = games_played + 1"),
                     (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"increment_games_played error: {e}")


def increment_games_won(user_id):
    try:
        conn = Connection()
        conn.execute(q("INSERT INTO points (user_id, games_won) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET games_won = games_won + 1"),
                     (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"increment_games_won error: {e}")


def get_leaderboard(limit=10):
    try:
        conn = Connection()
        cur = conn.execute(q("SELECT user_id, points, games_played, games_won FROM points ORDER BY points DESC LIMIT ?"), (limit,))
        col_keys = [d[0] for d in cur.description] if USE_PG else None
        rows = cur.fetchall()
        conn.close()
        if USE_PG:
            return [dict(zip(col_keys, r)) for r in rows]
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"get_leaderboard error: {e}")
        return []


def log_game(game_type, player_count, winner_team, summary_dict):
    conn = Connection()
    conn.execute(
        q("INSERT INTO game_logs (timestamp, game_type, player_count, winner_team, summary) VALUES (?, ?, ?, ?, ?)"),
        (datetime.utcnow().isoformat(), game_type, player_count, winner_team, json.dumps(summary_dict))
    )
    conn.commit()
    conn.close()


def get_config(key):
    conn = Connection()
    cur = conn.execute(q("SELECT value FROM config WHERE key = ?"), (key,))
    row = cur.fetchone()
    conn.close()
    if USE_PG:
        return row[0] if row else None
    return row[0] if row else None


def set_config(key, value):
    conn = Connection()
    if USE_PG:
        conn.execute(q("INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"),
                     (key, str(value)))
    else:
        conn.execute(q("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)"), (key, str(value)))
    conn.commit()
    conn.close()


def wipe_all_points():
    conn = Connection()
    conn.execute("DELETE FROM points")
    conn.commit()
    conn.close()


def get_top_player():
    conn = Connection()
    cur = conn.execute("SELECT user_id, points FROM points ORDER BY points DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if row:
        return {"user_id": row[0], "points": row[1], "name": f"<@{row[0]}>"}
    return None
