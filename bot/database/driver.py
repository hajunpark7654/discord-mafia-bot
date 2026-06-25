import os
import sqlite3

_DATABASE_URL = None  # exported for diagnostics

# Railway Beta v2: variables may not be in os.environ, check secret files
_env_val = os.getenv("DATABASE_URL")
if _env_val:
    _DATABASE_URL = _env_val
else:
    for path in ("/etc/secrets/DATABASE_URL", "/etc/secrets/DATABASE_URL.txt"):
        try:
            with open(path) as f:
                _DATABASE_URL = f.read().strip()
                break
        except:
            pass
    if not _DATABASE_URL:
        import dotenv
        dotenv.load_dotenv()
        _DATABASE_URL = os.getenv("DATABASE_URL")

USE_PG = _DATABASE_URL is not None

if USE_PG:
    import psycopg2
    import psycopg2.extras

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "mafia_bot.db")


class Connection:
    def __init__(self):
        if USE_PG:
            self._raw = psycopg2.connect(_DATABASE_URL)
            self._raw.autocommit = False
        else:
            self._raw = sqlite3.connect(DB_PATH)
            self._raw.row_factory = sqlite3.Row

    def execute(self, sql, params=None):
        cur = self._raw.cursor()
        if USE_PG:
            sql = sql.replace("?", "%s")
        cur.execute(sql, params or ())
        return cur

    def commit(self):
        self._raw.commit()

    def close(self):
        self._raw.close()

    def lastrowid(self, cur):
        if USE_PG:
            return cur.fetchone()[0]
        return cur.lastrowid


def q(sql):
    if USE_PG:
        sql = sql.replace("?", "%s")
    return sql
