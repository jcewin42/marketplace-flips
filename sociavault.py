"""Thin wrapper around the SociaVault Marketplace API.

Real (observed) response shape for the search endpoint - this does NOT
match SociaVault's own blog docs, which is why several fields below
are named for what the API actually sends rather than what's
documented:

    {
      "success": true,
      "data": {
        "success": true,
        "listings": {
          "0": { "id": ..., "title": ..., "creation_time": null, ... },
          "1": { ... }
        }
      },
      "credits_used": 3
    }

Notable surprises vs. the docs:
  - Double-wrapped: listings live at data.listings, not top-level.
  - listings is a dict keyed by stringified index ("0", "1", ...), not
    a JSON array.
  - creation_time is a real field (confirms it exists but is null in
    practice, as observed in testing before this file existed).
  - category comes back as category_id (a numeric id), not a text
    category label.
  - credits_used is present at the top level - worth logging every
    call, since it's the most direct signal of actual API cost.

The item endpoint likely has a similar envelope (unconfirmed - we
haven't wired it up yet). When you build Stage 2, check
get_listing_details's raw response the same way this file's dev
history did, rather than assuming it matches the blog docs.
"""
import logging

import requests

from config import SOCIAVAULT_API_KEY

logger = logging.getLogger(__name__)

BASE_URL = "https://api.sociavault.com"


def search_marketplace(query: str, latitude: float, longitude: float, radius: int) -> list:
    """Cheap search endpoint. Returns a list of raw listing dicts.

    NOTE on pagination: unconfirmed for this endpoint's real shape -
    the docs mention a cursor but we haven't seen one in a real
    response yet. Revisit if searches start looking capped.
    """
    url = f"{BASE_URL}/v1/scrape/facebook-marketplace/search"
    params = {
        "query": query,
        "lat": latitude,
        "lng": longitude,
        "radius_km": radius,
        "sort_by": "creation_time_descend",
    }
    logger.debug("GET %s params=%s", url, params)

    response = requests.get(
        url,
        headers={"x-api-key": SOCIAVAULT_API_KEY},
        params=params,
        timeout=15,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError:
        logger.error(
            "SociaVault search failed: HTTP %d - %s",
            response.status_code, response.text[:500],
        )
        raise

    payload = response.json()
    inner = payload.get("data") or {}
    listings_obj = inner.get("listings") or {}
    # listings comes back as a dict keyed by stringified index, not a
    # JSON array - values() gives us a normal list, and json parsing
    # preserves insertion order so this stays in the original order.
    results = list(listings_obj.values()) if isinstance(listings_obj, dict) else list(listings_obj)

    logger.info(
        "SociaVault search returned %d results (credits_used=%s)",
        len(results), payload.get("credits_used"),
    )
    if not results and "listings" not in inner:
        logger.warning(
            "Unexpected response shape - top-level keys: %s, data keys: %s",
            list(payload.keys()), list(inner.keys()),
        )
    return results


def get_listing_details(listing_id: str) -> dict:
    """More expensive full-listing endpoint (includes description).
    Only call this for listings that passed Stage 1 filtering.

    UNCONFIRMED: haven't actually hit this endpoint yet, so the same
    double-wrapping search had ("data" envelope) may well apply here
    too. Check the raw response the first time you call this for real
    rather than assuming this return shape is right.
    """
    url = f"{BASE_URL}/v1/scrape/facebook-marketplace/item"
    logger.debug("GET %s id=%s", url, listing_id)

    response = requests.get(
        url,
        headers={"x-api-key": SOCIAVAULT_API_KEY},
        params={"id": listing_id},
        timeout=15,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError:
        logger.error(
            "SociaVault listing detail fetch failed for %s: HTTP %d - %s",
            listing_id, response.status_code, response.text[:500],
        )
        raise

    payload = response.json()
    return payload.get("data", payload)


def normalize_listing(raw: dict) -> dict:
    """Maps SociaVault's nested response shape into the flat dict the
    db and AI filtering code expect."""
    price = raw.get("price") or {}
    location = raw.get("location") or {}
    photo = raw.get("primary_photo") or {}
    return {
        "id": raw.get("id"),
        "url": raw.get("url"),
        "title": raw.get("title"),
        "price_amount": price.get("amount"),
        "price_formatted": price.get("formatted_amount"),
        "location_city": location.get("city"),
        "location_state": location.get("state"),
        "primary_photo_url": photo.get("url"),
        "category": raw.get("category_id"),
        "is_live": raw.get("is_live"),
        "is_sold": raw.get("is_sold"),
        # Real field is creation_time (confirmed present, null in
        # practice so far) - not "listed_at" as the blog docs implied.
        "listed_at": raw.get("creation_time"),
    }
