# db.py
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "mocktest.db"

class DB:
    def __init__(self, path=DB_PATH):
        self.path = path
        self._ensure()

    def _ensure(self):
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON;")

    def run_script(self, script_path):
        with open(script_path, "r", encoding="utf-8") as f:
            self.conn.executescript(f.read())
            self.conn.commit()

    def execute(self, sql, params=()):
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def fetch_all(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def fetch_one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def close(self):
        self.conn.close()
