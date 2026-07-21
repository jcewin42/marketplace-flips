"""SQLite schema and helpers. Every function takes a db path or an open
connection - nothing here is specific to any one search, which is what
lets each search config point at its own database file.

Schema includes columns for Stage 1/2 AI results and a listing_feedback
table up front, even though the Jetson filtering and Discord feedback
buttons aren't built yet. Adding columns to a live table later is
annoying; adding them now costs nothing.

Note the distinction between first_seen_at and listing_created_at:
first_seen_at is when *we* first saw the listing (always known, set on
insert). listing_created_at is when the seller actually posted it on
Marketplace - only available from the full-listing endpoint, so it
stays NULL until Stage 2 fills it in. Once populated, listing_created_at
is what you'd bucket into a histogram to see when relevant listings
tend to get posted; first_seen_at - listing_created_at tells you how
long it took your polling schedule to catch a given listing.

_ensure_column() below is a lightweight migration helper: since
CREATE TABLE IF NOT EXISTS only handles brand-new databases, any new
column added to SCHEMA after a database already exists (like this one)
also needs a line here so existing databases on the Pi pick it up
without having to be deleted and recreated.
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
    listing_created_at TIMESTAMP,
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

-- Small key/value table for monitor state that needs to survive
-- restarts (currently just last_check_at, but generic in case other
-- persisted state comes up later).
CREATE TABLE IF NOT EXISTS monitor_state (
    key TEXT PRIMARY KEY,
    value TEXT
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


def _ensure_column(conn, table: str, column: str, coltype: str):
    """Adds `column` to `table` if it doesn't already exist. Safe to
    call repeatedly - checks PRAGMA table_info first. Use this for any
    schema change made to a table after it may already exist on some
    machine (i.e. basically every change from now on)."""
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")


def init_db(db_path: str):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        # Migrations for columns added after a database may already
        # exist. Add a line here (not just in SCHEMA above) whenever a
        # new column is introduced.
        _ensure_column(conn, "listings", "listing_created_at", "TIMESTAMP")


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


def update_listing_created_at(conn, listing_id: str, created_at: datetime):
    """Records when the listing was actually posted on Marketplace, per
    the full-listing endpoint. Not available from search results, so
    this only gets called once Stage 2 fetches listing details."""
    conn.execute(
        "UPDATE listings SET listing_created_at = ? WHERE id = ?",
        (created_at.isoformat(), listing_id),
    )


def get_last_check(conn):
    """Returns the last check time as a UTC-aware datetime, or None if
    the monitor has never run against this database before."""
    row = conn.execute("SELECT value FROM monitor_state WHERE key = 'last_check_at'").fetchone()
    if row is None:
        return None
    return datetime.fromisoformat(row["value"])


def set_last_check(conn, when: datetime):
    conn.execute(
        "INSERT INTO monitor_state (key, value) VALUES ('last_check_at', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (when.isoformat(),),
    )
