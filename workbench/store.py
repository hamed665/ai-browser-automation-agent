"""Small persistent task state machine with atomic transitions."""

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime


class Store:
    def __init__(self, path):
        self.path = path
        with self.connection() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, spec TEXT NOT NULL, state TEXT NOT NULL, result TEXT);
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, at TEXT, state TEXT);
            """)
        os.chmod(path, 0o600)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, spec):
        task_id = str(uuid.uuid4())
        with self.connection() as db:
            db.execute(
                "INSERT INTO tasks VALUES (?, ?, 'pending', NULL)",
                (task_id, json.dumps(spec, sort_keys=True)),
            )
            self.event(db, task_id, "pending")
        return self.get(task_id)

    def event(self, db, task_id, state):
        db.execute(
            "INSERT INTO events(task_id,at,state) VALUES (?,?,?)",
            (task_id, datetime.now(UTC).isoformat(), state),
        )

    def get(self, task_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["spec"] = json.loads(result["spec"])
            result["result"] = json.loads(result["result"]) if result["result"] else None
            result["events"] = [
                dict(r)
                for r in db.execute(
                    "SELECT seq,at,state FROM events WHERE task_id=? ORDER BY seq", (task_id,)
                )
            ]
            return result

    def list(self):
        with self.connection() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM tasks ORDER BY rowid DESC LIMIT 100")]
        return [self.get(task_id) for task_id in ids]

    def transition(self, task_id, before, after, result=None):
        allowed = {
            ("pending", "approved"),
            ("pending", "rejected"),
            ("approved", "running"),
            ("running", "succeeded"),
            ("running", "failed"),
        }
        if (before, after) not in allowed:
            raise ValueError("Invalid transition")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE tasks SET state=?,result=? WHERE id=? AND state=?",
                (after, json.dumps(result), task_id, before),
            ).rowcount
            if changed != 1:
                return False
            self.event(db, task_id, after)
        return True
