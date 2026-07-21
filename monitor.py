"""Main orchestrator. Deliberately knows nothing about outboard motors,
HP, or any other search-specific detail - all of that lives in the
active SearchConfig. Adding a second search later means adding a new
search_configs/*.py file and changing ACTIVE_SEARCH; this file doesn't
change.
"""
import json
import logging
import sys
import time
from datetime import datetime

import ai_filter
import config
import db
import discord_notify
import sociavault
from logging_setup import configure_logging
from schedule import EASTERN, seconds_until_next_check

logger = logging.getLogger(__name__)


def parse_listed_at(value: str):
    """Parses the listed_at timestamp SociaVault sometimes includes on
    search results (e.g. '2026-05-15T14:22:00Z'). Returns None on any
    parse failure rather than raising - this is a nice-to-have field,
    not worth crashing a check over."""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def check_for_new_listings(cfg, conn):
    logger.info("Checking for new listings (query=%r)", cfg.query)
    raw_results = sociavault.search_marketplace(
        query=cfg.query, latitude=cfg.latitude, longitude=cfg.longitude, radius=cfg.radius,
    )
    logger.info("Search returned %d raw results", len(raw_results))

    new_count = 0
    duplicate_count = 0
    negative_keyword_count = 0

    for raw in raw_results:
        listing = sociavault.normalize_listing(raw)
        if not listing.get("id"):
            logger.warning("Skipping result with no listing id: %r", raw)
            continue

        title_lower = (listing.get("title") or "").lower()
        if any(neg.lower() in title_lower for neg in cfg.negative_keywords):
            negative_keyword_count += 1
            logger.debug("Skipping %r - matched a negative keyword", listing.get("title"))
            continue

        if db.listing_exists(conn, listing["id"]):
            db.touch_listing(conn, listing["id"])
            duplicate_count += 1
            continue

        new_count += 1
        logger.info(
            "New listing: %r (%s) %s",
            listing.get("title"), listing.get("price_formatted"), listing.get("url"),
        )
        db.insert_listing(conn, listing, raw_json=json.dumps(raw))

        if listing.get("listed_at"):
            created_at = parse_listed_at(listing["listed_at"])
            if created_at:
                db.update_listing_created_at(conn, listing["id"], created_at)
            else:
                logger.warning("Could not parse listed_at %r for %r", listing["listed_at"], listing.get("title"))

        stage1_result = ai_filter.filter_stage1(listing)
        logger.info(
            "Stage 1 classified %r as %s (reason: %s)",
            listing.get("title"), stage1_result["category"], stage1_result.get("reason"),
        )
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
            logger.info("Notified Discord for %r", listing.get("title"))

    logger.info(
        "Check complete: %d new, %d duplicates, %d filtered by negative keyword",
        new_count, duplicate_count, negative_keyword_count,
    )


def run():
    configure_logging()
    config.validate()

    cfg = config.load_active_config()
    logger.info("Starting monitor for search '%s'", cfg.name)
    db.init_db(cfg.database_path)

    if "--once" in sys.argv:
        logger.info("--once passed: running a single check and exiting")
        with db.get_connection(cfg.database_path) as conn:
            check_for_new_listings(cfg, conn)
            db.set_last_check(conn, datetime.now(EASTERN))
        return

    with db.get_connection(cfg.database_path) as conn:
        last_check = db.get_last_check(conn)
    if last_check is None:
        # First time this database has ever run - fine to check
        # immediately rather than waiting a full interval.
        last_check = datetime.min.replace(tzinfo=EASTERN)
        logger.info("No previous check found in database - running first check now")
    else:
        logger.info("Last check was: %s", last_check)

    while True:
        wait_seconds = seconds_until_next_check(last_check)
        if wait_seconds > 0:
            sleep_for = min(wait_seconds, 60)
            logger.debug("Sleeping %.0fs before next check", sleep_for)
            time.sleep(sleep_for)
            continue

        last_check = datetime.now(EASTERN)
        with db.get_connection(cfg.database_path) as conn:
            try:
                check_for_new_listings(cfg, conn)
            except Exception:
                logger.exception("Error during check")
            # Persist even on failure - a failing API shouldn't cause
            # tight retry loops that ignore the schedule.
            db.set_last_check(conn, last_check)


if __name__ == "__main__":
    run()
