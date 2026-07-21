"""SQLite schema and helpers. Every function takes a db path or an open
connection - nothing here is specific to any one search, which is what
lets each search config point at its own database file.

Schema includes columns for Stage 1/2 AI results and a listing_feedback
table up front, even though the Jetson filtering and Discord feedback
buttons aren't built yet. Adding columns to a live table later is
annoying; adding them now costs nothing.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id TEXT PRIMARY KEY,
    url TEXT,
    title TEXT,
    price_amount INTEGER,
    price_formatted TEXT,
    location_city TEXT,
    location_state TEXT,
    primary_photo_url TEXT,
    category TEXT,
    is_live BOOLEAN,
    is_sold BOOLEAN,
    description TEXT,
    ai_stage1_category TEXT,
    ai_stage1_confidence REAL,
    ai_stage1_reason TEXT,
    ai_stage2_category TEXT,
    ai_stage2_confidence REAL,
    ai_stage2_reason TEXT,
    notified_at TIMESTAMP,
    first_seen_at TIMESTAMP,
    last_seen_at TIMESTAMP,
    raw_search_json TEXT
);

CREATE TABLE IF NOT EXISTS listing_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id TEXT REFERENCES listings(id),
    ai_category TEXT,
    user_category TEXT,
    feedback_reason TEXT,
    created_at TIMESTAMP
);
"""


@contextmanager
def get_connection(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)


def listing_exists(conn, listing_id: str) -> bool:
    return conn.execute("SELECT 1 FROM listings WHERE id = ?", (listing_id,)).fetchone() is not None


def insert_listing(conn, listing: dict, raw_json: str):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO listings (
            id, url, title, price_amount, price_formatted,
            location_city, location_state, primary_photo_url, category,
            is_live, is_sold, first_seen_at, last_seen_at, raw_search_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            listing["id"], listing.get("url"), listing.get("title"),
            listing.get("price_amount"), listing.get("price_formatted"),
            listing.get("location_city"), listing.get("location_state"),
            listing.get("primary_photo_url"), listing.get("category"),
            listing.get("is_live"), listing.get("is_sold"),
            now, now, raw_json,
        ),
    )


def touch_listing(conn, listing_id: str):
    """Update last_seen_at for a listing we've already stored - lets us
    later tell how long a listing stayed live."""
    conn.execute(
        "UPDATE listings SET last_seen_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), listing_id),
    )


def update_ai_stage1(conn, listing_id: str, category: str, confidence, reason: str):
    conn.execute(
        """UPDATE listings SET ai_stage1_category = ?, ai_stage1_confidence = ?,
           ai_stage1_reason = ? WHERE id = ?""",
        (category, confidence, reason, listing_id),
    )


def mark_notified(conn, listing_id: str):
    conn.execute(
        "UPDATE listings SET notified_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), listing_id),
    )
