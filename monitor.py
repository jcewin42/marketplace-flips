"""Main orchestrator. Deliberately knows nothing about outboard motors,
HP, or any other search-specific detail - all of that lives in the
active SearchConfig. Adding a second search later means adding a new
search_configs/*.py file and changing ACTIVE_SEARCH; this file doesn't
change.
"""
import json
import time
from datetime import datetime

import ai_filter
import db
import discord_notify
import sociavault
from config import load_active_config
from schedule import EASTERN, seconds_until_next_check


def check_for_new_listings(cfg, conn):
    raw_results = sociavault.search_marketplace(
        query=cfg.query, latitude=cfg.latitude, longitude=cfg.longitude, radius=cfg.radius,
    )

    for raw in raw_results:
        listing = sociavault.normalize_listing(raw)
        if not listing.get("id"):
            continue

        title_lower = (listing.get("title") or "").lower()
        if any(neg.lower() in title_lower for neg in cfg.negative_keywords):
            continue

        if db.listing_exists(conn, listing["id"]):
            db.touch_listing(conn, listing["id"])
            continue

        db.insert_listing(conn, listing, raw_json=json.dumps(raw))

        stage1_result = ai_filter.filter_stage1(listing)
        db.update_ai_stage1(
            conn, listing["id"],
            stage1_result["category"], stage1_result.get("confidence"), stage1_result.get("reason"),
        )

        # TODO: once the full-listing endpoint + Stage 2 are wired in,
        # fetch the description and run filter_stage2 before notifying,
        # instead of notifying straight off the Stage 1 result.
        if stage1_result["category"] != "IRRELEVANT":
            discord_notify.send_notification(listing, stage1_result)
            db.mark_notified(conn, listing["id"])


def run():
    cfg = load_active_config()
    db.init_db(cfg.database_path)
    print(f"Monitoring '{cfg.name}' -> {cfg.database_path}")

    last_check = datetime.min.replace(tzinfo=EASTERN)

    while True:
        wait_seconds = seconds_until_next_check(last_check)
        if wait_seconds > 0:
            time.sleep(min(wait_seconds, 60))
            continue

        last_check = datetime.now(EASTERN)
        with db.get_connection(cfg.database_path) as conn:
            try:
                check_for_new_listings(cfg, conn)
            except Exception as exc:
                print(f"Error during check: {exc}")


if __name__ == "__main__":
    run()
