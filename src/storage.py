"""Account-isolated cache. Failed refreshes never replace a complete cache entry."""
import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path


def data_dir():
    p = Path(os.getenv('SEO_DATA_DIR', '.data'))
    p.mkdir(mode=0o700, parents=True, exist_ok=True)
    p.chmod(0o700)
    return p


class Cache:
    def __init__(self, path=None, ttl=None):
        self.path = str(path or data_dir() / 'cache.sqlite')
        self.ttl = int(ttl or os.getenv('CACHE_TTL_SECONDS', '3600'))
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, created REAL)')
        Path(self.path).chmod(0o600)

    @staticmethod
    def key(account, source, payload):
        return hashlib.sha256(json.dumps([account, source, payload], sort_keys=True).encode()).hexdigest()

    def get(self, key, stale=False):
        with sqlite3.connect(self.path) as db:
            row = db.execute('SELECT value, created FROM cache WHERE key=?', (key,)).fetchone()
        if row and (stale or time.time() - row[1] < self.ttl):
            return json.loads(row[0]), row[1]
        return None

    def put(self, key, value):
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)', (key, json.dumps(value), time.time()))


def settings(account, value=None):
    p = data_dir() / (hashlib.sha256(account.encode()).hexdigest() + '.json')
    if value is not None:
        p.write_text(json.dumps(value, indent=2))
        p.chmod(0o600)
    return json.loads(p.read_text()) if p.exists() else {}
