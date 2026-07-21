"""Sends Discord notifications one at a time with a delay between
messages, since sending many at once previously hit HTTP 429 (Discord
webhook rate limit).

Heads up for the future feedback-buttons feature: a plain incoming
webhook (what this uses) can't attach interactive buttons - Discord
only allows buttons/components on messages sent by a bot via the bot
API, which also needs an interaction endpoint to receive clicks. When
you build that, this module will need to become a bot client instead
of a webhook poster. Not needed yet, just flagging it now so it's not
a surprise later.
"""
import logging
import time

import requests

from config import DISCORD_WEBHOOK_URL

logger = logging.getLogger(__name__)

DELAY_BETWEEN_MESSAGES_SECONDS = 2


def send_notification(listing: dict, ai_result: dict):
    if not DISCORD_WEBHOOK_URL:
        logger.warning("DISCORD_WEBHOOK_URL not set - skipping notification for %r", listing.get("title"))
        return

    embed = {
        "title": listing.get("title") or "Listing",
        "url": listing.get("url"),
        "description": ai_result.get("reason", ""),
        "fields": [
            {"name": "Price", "value": listing.get("price_formatted") or "N/A", "inline": True},
            {
                "name": "Location",
                "value": f"{listing.get('location_city', '')}, {listing.get('location_state', '')}",
                "inline": True,
            },
            {"name": "AI Category", "value": ai_result.get("category", "UNKNOWN"), "inline": True},
        ],
    }
    if listing.get("primary_photo_url"):
        embed["image"] = {"url": listing["primary_photo_url"]}

    payload = {"embeds": [embed]}
    response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)

    if response.status_code == 429:
        retry_after = response.json().get("retry_after", 5)
        logger.warning("Discord rate limited - retrying after %.1fs", retry_after)
        time.sleep(retry_after)
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)

    if response.status_code >= 400:
        logger.error(
            "Discord notification failed for %r: HTTP %d - %s",
            listing.get("title"), response.status_code, response.text[:500],
        )
    else:
        logger.debug("Discord notification sent for %r", listing.get("title"))

    time.sleep(DELAY_BETWEEN_MESSAGES_SECONDS)
