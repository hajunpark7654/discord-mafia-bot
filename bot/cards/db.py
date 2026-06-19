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
            template_id INTEGER NOT NULL REFERENCES card_templates(id),
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
            quote TEXT DEFAULT ''
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
        conn.commit()
    conn.close()


def add_card_template(name, health=1000, attack=500, speed=200, rarity="F", image_url="", catch_image_url="", shiny_catch_image_url="", mythical_catch_image_url="", quote=""):
    conn = Connection()
    if USE_PG:
        conn.execute(q("INSERT INTO card_templates (name, health, attack, speed, rarity, image_url, catch_image_url, shiny_catch_image_url, mythical_catch_image_url, quote) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (name) DO NOTHING"),
                     (name, health, attack, speed, rarity, image_url, catch_image_url, shiny_catch_image_url, mythical_catch_image_url, quote))
    else:
        conn.execute(q("INSERT OR IGNORE INTO card_templates (name, health, attack, speed, rarity, image_url, catch_image_url, shiny_catch_image_url, mythical_catch_image_url, quote) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"),
                     (name, health, attack, speed, rarity, image_url, catch_image_url, shiny_catch_image_url, mythical_catch_image_url, quote))
    conn.commit()
    conn.close()


def get_all_templates():
    conn = Connection()
    cur = conn.execute("SELECT * FROM card_templates")
    col_keys = [d[0] for d in cur.description] if USE_PG else None
    rows = cur.fetchall()
    conn.close()
    if USE_PG:
        return [dict(zip(col_keys, r)) for r in rows]
    return [dict(r) for r in rows]


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
    conn = Connection()
    cur = conn.execute("SELECT * FROM card_templates ORDER BY RANDOM() LIMIT 1")
    col_keys = [d[0] for d in cur.description] if USE_PG else None
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    if USE_PG:
        return dict(zip(col_keys, row))
    return dict(row)


def insert_card_instance(owner_id, template_id, health, attack, speed, h_mod, a_mod, s_mod, is_shiny, is_mythical, rarity, ovr):
    conn = Connection()
    if USE_PG:
        cur = conn.execute(
            q("INSERT INTO card_instances (owner_id, template_id, health, attack, speed, health_mod, attack_mod, speed_mod, is_shiny, is_mythical, rarity, ovr) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id"),
            (owner_id, template_id, health, attack, speed, h_mod, a_mod, s_mod, 1 if is_shiny else 0, 1 if is_mythical else 0, rarity, ovr)
        )
        card_id = cur.fetchone()[0]
    else:
        cur = conn.execute(
            q("INSERT INTO card_instances (owner_id, template_id, health, attack, speed, health_mod, attack_mod, speed_mod, is_shiny, is_mythical, rarity, ovr) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"),
            (owner_id, template_id, health, attack, speed, h_mod, a_mod, s_mod, 1 if is_shiny else 0, 1 if is_mythical else 0, rarity, ovr)
        )
        card_id = cur.lastrowid
    conn.commit()
    conn.close()
    return card_id


def get_player_cards(owner_id):
    conn = Connection()
    cur = conn.execute(
        q("""SELECT ci.*, ct.name as card_name, ct.image_url, ct.shiny_catch_image_url, ct.mythical_catch_image_url, ct.quote
            FROM card_instances ci
            JOIN card_templates ct ON ci.template_id = ct.id
            WHERE ci.owner_id = ?
            ORDER BY
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
        q("""SELECT ci.*, ct.name as card_name, ct.image_url, ct.shiny_catch_image_url, ct.mythical_catch_image_url, ct.quote
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
        q("""SELECT ct.name, ct.id as template_id,
            COUNT(ci.id) as total,
            SUM(CASE WHEN ci.is_shiny = 1 THEN 1 ELSE 0 END) as shiny_count,
            SUM(CASE WHEN ci.is_mythical = 1 THEN 1 ELSE 0 END) as mythical_count
            FROM card_templates ct
            LEFT JOIN card_instances ci ON ci.template_id = ct.id AND ci.owner_id = ?
            GROUP BY ct.id ORDER BY ct.name"""),
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
