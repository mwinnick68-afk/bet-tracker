from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

DEFAULT_DB_PATH: Final[Path] = Path("data/bets.db")


def get_db_path(path: str | None) -> Path:
    return DEFAULT_DB_PATH if path is None else Path(path)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bets (
          id INTEGER PRIMARY KEY,
          date TEXT NOT NULL,
          sport TEXT NOT NULL,
          book TEXT NOT NULL,
          type TEXT NOT NULL,
          team_or_player TEXT NOT NULL,
          odds_american REAL NOT NULL,
          stake REAL NOT NULL,
          result TEXT NOT NULL,
          notes TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          UNIQUE(date, sport, book, type, team_or_player, odds_american, stake, result, notes)
        )
        """
    )
    conn.commit()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
