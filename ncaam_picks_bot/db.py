from __future__ import annotations

import hashlib
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from zoneinfo import ZoneInfo

from ncaam_picks_bot.parser import ParsedPick, RejectedLine

LOGGER = logging.getLogger(__name__)
NY_TZ = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class MessageRecord:
    message_id: str
    author_id: str
    channel_id: str
    created_at: str
    is_correction: int
    content_hash: str
    raw_content: str


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS messages (
            message_id TEXT PRIMARY KEY,
            author_id TEXT,
            channel_id TEXT,
            created_at TEXT,
            is_correction INTEGER,
            content_hash TEXT,
            raw_content TEXT
        );

        CREATE TABLE IF NOT EXISTS picks (
            pick_id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT,
            line_no INTEGER,
            pick_date TEXT,
            team TEXT,
            opponent TEXT,
            spread REAL,
            relation TEXT CHECK(relation IN ('at','over')),
            status TEXT CHECK(status IN ('pending','win','loss','push','void','replaced')) DEFAULT 'pending',
            odds INTEGER DEFAULT -110,
            risk REAL DEFAULT 1.0,
            units REAL,
            replaces_pick_id INTEGER,
            replaced_by_pick_id INTEGER,
            raw_line TEXT,
            matchup_key TEXT,
            FOREIGN KEY(message_id) REFERENCES messages(message_id)
        );

        CREATE TABLE IF NOT EXISTS rejected_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT,
            line_no INTEGER,
            raw_line TEXT,
            reason TEXT
        );

        CREATE UNIQUE INDEX IF NOT EXISTS uniq_message_line ON picks(message_id, line_no);
        CREATE INDEX IF NOT EXISTS idx_matchup_date ON picks(matchup_key, pick_date, pick_id);
        """
    )
    conn.commit()


def build_message_record(
    message_id: str,
    author_id: str,
    channel_id: str,
    created_at: datetime,
    is_correction: bool,
    raw_content: str,
) -> MessageRecord:
    content_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
    created_iso = created_at.isoformat()
    return MessageRecord(
        message_id=message_id,
        author_id=author_id,
        channel_id=channel_id,
        created_at=created_iso,
        is_correction=1 if is_correction else 0,
        content_hash=content_hash,
        raw_content=raw_content,
    )


def insert_message(conn: sqlite3.Connection, record: MessageRecord) -> bool:
    try:
        conn.execute(
            """
            INSERT INTO messages (
                message_id, author_id, channel_id, created_at, is_correction, content_hash, raw_content
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.message_id,
                record.author_id,
                record.channel_id,
                record.created_at,
                record.is_correction,
                record.content_hash,
                record.raw_content,
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        LOGGER.info("Message %s already processed; skipping.", record.message_id)
        return False


def pick_date_from_created(created_at: datetime) -> str:
    localized = created_at.astimezone(NY_TZ)
    return localized.date().isoformat()


def insert_picks(
    conn: sqlite3.Connection,
    message_id: str,
    pick_date: str,
    picks: Iterable[ParsedPick],
    is_correction: bool,
) -> tuple[int, int]:
    inserted = 0
    replaced = 0

    for pick in picks:
        if is_correction:
            replaced += apply_correction(conn, message_id, pick_date, pick)
            inserted += 1
        else:
            if insert_pick_row(conn, message_id, pick_date, pick):
                inserted += 1

    conn.commit()
    return inserted, replaced


def apply_correction(
    conn: sqlite3.Connection,
    message_id: str,
    pick_date: str,
    pick: ParsedPick,
) -> int:
    cursor = conn.execute(
        """
        SELECT pick_id
        FROM picks
        WHERE matchup_key = ?
          AND status NOT IN ('replaced', 'void')
        ORDER BY pick_id DESC
        LIMIT 1
        """,
        (pick.matchup_key,),
    )
    row = cursor.fetchone()
    new_pick_id = insert_pick_row(conn, message_id, pick_date, pick, status="pending")

    if not new_pick_id:
        return 0

    if row:
        old_pick_id = row["pick_id"]
        conn.execute(
            """
            UPDATE picks
            SET status = 'replaced', replaced_by_pick_id = ?
            WHERE pick_id = ?
            """,
            (new_pick_id, old_pick_id),
        )
        conn.execute(
            """
            UPDATE picks
            SET replaces_pick_id = ?
            WHERE pick_id = ?
            """,
            (old_pick_id, new_pick_id),
        )
        LOGGER.info("Replaced pick %s with %s", old_pick_id, new_pick_id)
        return 1

    LOGGER.info("No prior pick found for correction matchup_key=%s", pick.matchup_key)
    return 0


def insert_pick_row(
    conn: sqlite3.Connection,
    message_id: str,
    pick_date: str,
    pick: ParsedPick,
    status: str = "pending",
) -> int | None:
    try:
        cursor = conn.execute(
            """
            INSERT INTO picks (
                message_id, line_no, pick_date, team, opponent, spread, relation,
                status, raw_line, matchup_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                pick.line_no,
                pick_date,
                pick.team,
                pick.opponent,
                pick.spread,
                pick.relation,
                status,
                pick.raw_line,
                pick.matchup_key,
            ),
        )
        return int(cursor.lastrowid)
    except sqlite3.IntegrityError:
        LOGGER.warning(
            "Duplicate pick line; message_id=%s line_no=%s", message_id, pick.line_no
        )
        return None


def insert_rejected_lines(
    conn: sqlite3.Connection,
    message_id: str,
    rejected_lines: Iterable[RejectedLine],
) -> int:
    inserted = 0
    for rejection in rejected_lines:
        conn.execute(
            """
            INSERT INTO rejected_lines (message_id, line_no, raw_line, reason)
            VALUES (?, ?, ?, ?)
            """,
            (
                message_id,
                rejection.line_no,
                rejection.raw_line,
                rejection.reason,
            ),
        )
        inserted += 1
    conn.commit()
    return inserted


def list_pending(conn: sqlite3.Connection, pick_date: str) -> list[sqlite3.Row]:
    cursor = conn.execute(
        """
        SELECT * FROM picks
        WHERE pick_date = ?
          AND status NOT IN ('replaced', 'void')
        ORDER BY pick_id
        """,
        (pick_date,),
    )
    return list(cursor.fetchall())


def update_pick_grade(
    conn: sqlite3.Connection,
    pick_id: int,
    status: str,
    odds: int,
    risk: float,
    units: float,
) -> None:
    conn.execute(
        """
        UPDATE picks
        SET status = ?, odds = ?, risk = ?, units = ?
        WHERE pick_id = ?
        """,
        (status, odds, risk, units, pick_id),
    )
    conn.commit()


def fetch_stats_rows(
    conn: sqlite3.Connection, from_date: str | None, to_date: str | None
) -> list[sqlite3.Row]:
    query = """
        SELECT pick_date, status, risk, units
        FROM picks
        WHERE status != 'replaced'
    """
    params: list[str] = []
    if from_date:
        query += " AND pick_date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND pick_date <= ?"
        params.append(to_date)
    cursor = conn.execute(query, params)
    return list(cursor.fetchall())
