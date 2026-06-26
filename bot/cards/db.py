import random
from bot.database.driver import Connection, USE_PG, q


def init_card_tables():
    conn = Connection()
    if USE_PG:
        conn.execute("""CREATE TABLE IF NOT EXISTS card_templates (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            health INTEGER DEFAULT 1000,
            attack INTEGER DEFAULT 500,
            speed INTEGER DEFAULT 200,
            rarity TEXT DEFAULT 'F',
            image_url TEXT DEFAULT '',
            catch_image_url TEXT DEFAULT '',
            shiny_catch_image_url TEXT DEFAULT '',
            mythical_catch_image_url TEXT DEFAULT '',
            quote TEXT DEFAULT ''
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS card_instances (
            id SERIAL PRIMARY KEY,
            template_id INTEGER NOT NULL REFERENCES card_templates(id) ON DELETE CASCADE,
            owner_id BIGINT NOT NULL,
            health INTEGER NOT NULL,
            attack INTEGER NOT NULL,
            speed INTEGER NOT NULL,
            health_mod DOUBLE PRECISION DEFAULT 0,
            attack_mod DOUBLE PRECISION DEFAULT 0,
            speed_mod DOUBLE PRECISION DEFAULT 0,
            is_shiny INTEGER DEFAULT 0,
            is_mythical INTEGER DEFAULT 0,
            rarity TEXT NOT NULL,
            ovr INTEGER DEFAULT 0,
            obtained_at TEXT DEFAULT (NOW())
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS card_battles (
            id SERIAL PRIMARY KEY,
            player1_id BIGINT NOT NULL,
            player2_id BIGINT NOT NULL,
            winner_id BIGINT,
            status TEXT DEFAULT 'pending',
            started_at TEXT DEFAULT (NOW()),
            finished_at TEXT
        )""")
        conn.execute("ALTER TABLE card_templates ADD COLUMN IF NOT EXISTS shiny_catch_image_url TEXT DEFAULT ''")
        conn.execute("ALTER TABLE card_templates ADD COLUMN IF NOT EXISTS mythical_catch_image_url TEXT DEFAULT ''")
        conn.execute("ALTER TABLE card_templates ADD COLUMN IF NOT EXISTS is_special INTEGER DEFAULT 0")
        conn.execute("ALTER TABLE card_instances ADD COLUMN IF NOT EXISTS is_special INTEGER DEFAULT 0")
    else:
        conn.execute("""CREATE TABLE IF NOT EXISTS card_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            health INTEGER DEFAULT 1000,
            attack INTEGER DEFAULT 500,
            speed INTEGER DEFAULT 200,
            rarity TEXT DEFAULT 'F',
            image_url TEXT DEFAULT '',
            catch_image_url TEXT DEFAULT '',
            shiny_catch_image_url TEXT DEFAULT '',
            mythical_catch_image_url TEXT DEFAULT '',
            quote TEXT DEFAULT '',
            is_special INTEGER DEFAULT 0
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS card_instances (
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
            is_special INTEGER DEFAULT 0,
            rarity TEXT NOT NULL,
            ovr INTEGER DEFAULT 0,
            obtained_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (template_id) REFERENCES card_templates(id)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS card_battles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player1_id INTEGER NOT NULL,
            player2_id INTEGER NOT NULL,
            winner_id INTEGER,
            status TEXT DEFAULT 'pending',
            started_at TEXT DEFAULT (datetime('now')),
            finished_at TEXT
        )""")
    conn.commit()
    # Add new columns to existing databases
    if not USE_PG:
        try:
            conn.execute("ALTER TABLE card_templates ADD COLUMN shiny_catch_image_url TEXT DEFAULT ''")
        except:
            pass
        try:
            conn.execute("ALTER TABLE card_templates ADD COLUMN mythical_catch_image_url TEXT DEFAULT ''")
        except:
            pass
        try:
            conn.execute("ALTER TABLE card_templates ADD COLUMN is_special INTEGER DEFAULT 0")
        except:
            pass
        try:
            conn.execute("ALTER TABLE card_instances ADD COLUMN is_special INTEGER DEFAULT 0")
        except:
            pass
        conn.commit()
    conn.close()


def add_card_template(name, health=1000, attack=500, speed=200, rarity="F", image_url="", catch_image_url="", shiny_catch_image_url="", mythical_catch_image_url="", quote="", is_special=False):
    conn = Connection()
    if USE_PG:
        conn.execute(q("INSERT INTO card_templates (name, health, attack, speed, rarity, image_url, catch_image_url, shiny_catch_image_url, mythical_catch_image_url, quote, is_special) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (name) DO NOTHING"),
                     (name, health, attack, speed, rarity, image_url, catch_image_url, shiny_catch_image_url, mythical_catch_image_url, quote, 1 if is_special else 0))
    else:
        conn.execute(q("INSERT OR IGNORE INTO card_templates (name, health, attack, speed, rarity, image_url, catch_image_url, shiny_catch_image_url, mythical_catch_image_url, quote, is_special) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"),
                     (name, health, attack, speed, rarity, image_url, catch_image_url, shiny_catch_image_url, mythical_catch_image_url, quote, 1 if is_special else 0))
    conn.commit()
    conn.close()


def get_all_templates():
    conn = Connection()
    try:
        cur = conn.execute("SELECT * FROM card_templates")
        col_keys = [d[0] for d in cur.description] if USE_PG else None
        rows = cur.fetchall()
        conn.close()
        if USE_PG:
            return [dict(zip(col_keys, r)) for r in rows]
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"get_all_templates error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        conn.close()
        raise


def delete_card_template(name):
    conn = Connection()
    try:
        cur = conn.execute(q("SELECT id FROM card_templates WHERE LOWER(name) = LOWER(?)"), (name,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return 0
        tid = row[0]
        conn.execute(q("DELETE FROM card_instances WHERE template_id = ?"), (tid,))
        conn.execute(q("DELETE FROM card_templates WHERE id = ?"), (tid,))
        conn.commit()
        conn.close()
        return 1
    except Exception as e:
        print(f"Delete template error: {e}")
        conn.close()
        return 0


def get_template(template_id):
    conn = Connection()
    cur = conn.execute(q("SELECT * FROM card_templates WHERE id = ?"), (template_id,))
    col_keys = [d[0] for d in cur.description] if USE_PG else None
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    if USE_PG:
        return dict(zip(col_keys, row))
    return dict(row)


def get_random_template():
    from bot.database.db import get_config
    special_enabled = get_config("special_spawn_enabled") == "1"

    conn = Connection()
    if USE_PG:
        if special_enabled:
            cur = conn.execute("SELECT * FROM card_templates")
        else:
            cur = conn.execute("SELECT * FROM card_templates WHERE is_special = 0 OR is_special IS NULL")
    else:
        if special_enabled:
            cur = conn.execute("SELECT * FROM card_templates")
        else:
            cur = conn.execute("SELECT * FROM card_templates WHERE is_special = 0 OR is_special IS NULL")

    col_keys = [d[0] for d in cur.description] if USE_PG else None
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return None

    templates = []
    if USE_PG:
        templates = [dict(zip(col_keys, r)) for r in rows]
    else:
        templates = [dict(r) for r in rows]

    tiers = {"S": [], "A": [], "B": [], "C": [], "D": [], "F": []}
    for t in templates:
        r = t.get("rarity", "F")
        if r in tiers:
            tiers[r].append(t)
        else:
            tiers["F"].append(t)

    weights = {"S": 0.001, "A": 0.099, "B": 0.15, "C": 0.20, "D": 0.25, "F": 0.30}
    available = {k: v for k, v in tiers.items() if v}
    if not available:
        return None

    tier_labels = list(available.keys())
    tier_weights = [weights[t] for t in tier_labels]
    total = sum(tier_weights)
    tier_weights = [w / total for w in tier_weights]

    chosen_tier = random.choices(tier_labels, weights=tier_weights, k=1)[0]
    return random.choice(available[chosen_tier])


def get_random_template_for_mafia():
    conn = Connection()
    cur = conn.execute("SELECT * FROM card_templates WHERE is_special = 0 OR is_special IS NULL")
    col_keys = [d[0] for d in cur.description] if USE_PG else None
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return None

    templates = []
    if USE_PG:
        templates = [dict(zip(col_keys, r)) for r in rows]
    else:
        templates = [dict(r) for r in rows]

    tiers = {"S": [], "A": [], "B": [], "C": [], "D": [], "F": []}
    for t in templates:
        r = t.get("rarity", "F")
        if r in tiers:
            tiers[r].append(t)
        else:
            tiers["F"].append(t)

    # Mafia: only B/A/S tiers, weighted 60/35/5
    mafia_weights = {"B": 0.60, "A": 0.35, "S": 0.05}
    available = {k: v for k, v in tiers.items() if v and k in mafia_weights}
    if not available:
        # fallback to all tiers if none of B/A/S exist
        all_weights = {"S": 0.001, "A": 0.099, "B": 0.15, "C": 0.20, "D": 0.25, "F": 0.30}
        available = {k: v for k, v in tiers.items() if v}
        if not available:
            return None
        tier_labels = list(available.keys())
        tier_weights = [all_weights[t] for t in tier_labels]
    else:
        tier_labels = list(available.keys())
        tier_weights = [mafia_weights[t] for t in tier_labels]

    total = sum(tier_weights)
    tier_weights = [w / total for w in tier_weights]

    chosen_tier = random.choices(tier_labels, weights=tier_weights, k=1)[0]
    return random.choice(available[chosen_tier])


def insert_card_instance(owner_id, template_id, health, attack, speed, h_mod, a_mod, s_mod, is_shiny, is_mythical, rarity, ovr, is_special=0):
    conn = Connection()
    if USE_PG:
        cur = conn.execute(
            q("INSERT INTO card_instances (owner_id, template_id, health, attack, speed, health_mod, attack_mod, speed_mod, is_shiny, is_mythical, is_special, rarity, ovr) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id"),
            (owner_id, template_id, health, attack, speed, h_mod, a_mod, s_mod, 1 if is_shiny else 0, 1 if is_mythical else 0, 1 if is_special else 0, rarity, ovr)
        )
        card_id = cur.fetchone()[0]
    else:
        cur = conn.execute(
            q("INSERT INTO card_instances (owner_id, template_id, health, attack, speed, health_mod, attack_mod, speed_mod, is_shiny, is_mythical, is_special, rarity, ovr) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"),
            (owner_id, template_id, health, attack, speed, h_mod, a_mod, s_mod, 1 if is_shiny else 0, 1 if is_mythical else 0, 1 if is_special else 0, rarity, ovr)
        )
        card_id = cur.lastrowid
    conn.commit()
    conn.close()
    return card_id


def get_player_cards(owner_id):
    conn = Connection()
    cur = conn.execute(
        q("""SELECT ci.*, ct.name as card_name, ct.image_url, ct.catch_image_url, ct.shiny_catch_image_url, ct.mythical_catch_image_url, ct.quote
            FROM card_instances ci
            JOIN card_templates ct ON ci.template_id = ct.id
            WHERE ci.owner_id = ?
            ORDER BY
                CASE WHEN ci.is_special = 1 THEN 0 ELSE 1 END,
                ci.is_shiny DESC,
                ci.is_mythical DESC,
                CASE ci.rarity
                    WHEN 'S' THEN 0 WHEN 'A' THEN 1 WHEN 'B' THEN 2
                    WHEN 'C' THEN 3 WHEN 'D' THEN 4 WHEN 'F' THEN 5
                END,
                ci.ovr DESC"""),
        (owner_id,)
    )
    col_keys = [d[0] for d in cur.description] if USE_PG else None
    rows = cur.fetchall()
    conn.close()
    if USE_PG:
        return [dict(zip(col_keys, r)) for r in rows]
    return [dict(r) for r in rows]


def get_card_instance(card_id):
    conn = Connection()
    cur = conn.execute(
        q("""SELECT ci.*, ct.name as card_name, ct.image_url, ct.catch_image_url, ct.shiny_catch_image_url, ct.mythical_catch_image_url, ct.quote
            FROM card_instances ci
            JOIN card_templates ct ON ci.template_id = ct.id
            WHERE ci.id = ?"""),
        (card_id,)
    )
    col_keys = [d[0] for d in cur.description] if USE_PG else None
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    if USE_PG:
        return dict(zip(col_keys, row))
    return dict(row)


def transfer_card(card_id, new_owner_id):
    conn = Connection()
    conn.execute(q("UPDATE card_instances SET owner_id = ? WHERE id = ?"), (new_owner_id, card_id))
    conn.commit()
    conn.close()


def get_owned_template_ids(owner_id):
    conn = Connection()
    cur = conn.execute(q("SELECT DISTINCT ci.template_id FROM card_instances ci WHERE ci.owner_id = ?"), (owner_id,))
    rows = cur.fetchall()
    conn.close()
    return set(r[0] for r in rows)


def get_completion(owner_id):
    conn = Connection()
    cur = conn.execute(
        q("""SELECT ct.name, ct.id as template_id, ct.rarity,
            COUNT(ci.id) as total,
            SUM(CASE WHEN ci.is_shiny = 1 THEN 1 ELSE 0 END) as shiny_count,
            SUM(CASE WHEN ci.is_mythical = 1 THEN 1 ELSE 0 END) as mythical_count
            FROM card_templates ct
            LEFT JOIN card_instances ci ON ci.template_id = ct.id AND ci.owner_id = ?
            GROUP BY ct.id
            ORDER BY
                CASE WHEN ct.is_special = 1 THEN 0 ELSE 1 END,
                CASE ct.rarity
                    WHEN 'S' THEN 0 WHEN 'A' THEN 1 WHEN 'B' THEN 2
                    WHEN 'C' THEN 3 WHEN 'D' THEN 4 WHEN 'F' THEN 5
                END,
                ct.name"""),
        (owner_id,)
    )
    col_keys = [d[0] for d in cur.description] if USE_PG else None
    rows = cur.fetchall()
    conn.close()
    if USE_PG:
        return [dict(zip(col_keys, r)) for r in rows]
    return [dict(r) for r in rows]


def create_battle(player1_id, player2_id):
    conn = Connection()
    if USE_PG:
        cur = conn.execute(q("INSERT INTO card_battles (player1_id, player2_id, status) VALUES (?, ?, 'pending') RETURNING id"),
                           (player1_id, player2_id))
        battle_id = cur.fetchone()[0]
    else:
        cur = conn.execute(q("INSERT INTO card_battles (player1_id, player2_id, status) VALUES (?, ?, 'pending')"),
                           (player1_id, player2_id))
        battle_id = cur.lastrowid
    conn.commit()
    conn.close()
    return battle_id


def get_battle(battle_id):
    conn = Connection()
    cur = conn.execute(q("SELECT * FROM card_battles WHERE id = ?"), (battle_id,))
    col_keys = [d[0] for d in cur.description] if USE_PG else None
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    if USE_PG:
        return dict(zip(col_keys, row))
    return dict(row)


def finish_battle(battle_id, winner_id):
    conn = Connection()
    if USE_PG:
        conn.execute("UPDATE card_battles SET status = 'finished', winner_id = ?, finished_at = NOW() WHERE id = ?",
                     (winner_id, battle_id))
    else:
        conn.execute(q("UPDATE card_battles SET status = 'finished', winner_id = ?, finished_at = datetime('now') WHERE id = ?"),
                     (winner_id, battle_id))
    conn.commit()
    conn.close()
