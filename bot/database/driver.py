import os
import sqlite3

USE_PG = os.getenv("DATABASE_URL") is not None

if USE_PG:
    import psycopg2
    import psycopg2.extras

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "mafia_bot.db")


class Connection:
    def __init__(self):
        if USE_PG:
            self._raw = psycopg2.connect(os.environ["DATABASE_URL"])
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
