"""Thin wrapper around the SociaVault Marketplace API.

Per https://sociavault.com/blog/facebook-marketplace-scraper-api :
all endpoints take the API key in an `x-api-key` header, and there are
three endpoints - we only use two of them (we already have fixed
lat/lon per search config, so location-search isn't needed):

  search: /v1/scrape/facebook-marketplace/search
    params: query, latitude, longitude, radius_km (+ optional
    price_min/price_max/cursor). Returns {listings, cursor, total_count}.
    Up to 24 listings per page - see NOTE on pagination below.

  item: /v1/scrape/facebook-marketplace/item
    params: id. Returns full details including description.
"""
import logging

import requests

from config import SOCIAVAULT_API_KEY

logger = logging.getLogger(__name__)

BASE_URL = "https://api.sociavault.com"


def search_marketplace(query: str, latitude: float, longitude: float, radius: int) -> list:
    """Cheap search endpoint. Returns a list of raw listing dicts.

    NOTE on pagination: the docs say this returns up to 24 listings per
    page with a `cursor` for the next page. We're only fetching page 1
    right now - fine for a niche query like "outboard motor" in a
    single metro area, but if you ever see close to 24 results
    regularly, you're likely missing listings past the first page.
    """
    url = f"{BASE_URL}/v1/scrape/facebook-marketplace/search"
    # NOTE: the blog docs (linked above) show "latitude"/"longitude" as
    # the param names, but the live API actually rejects that with
    # "lat is required and must be a number" - the docs are wrong here,
    # trusting the API's own error message instead.
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

    data = response.json()
    results = data.get("listings", [])
    logger.info(
        "SociaVault search returned %d results (total_count=%s, cursor=%s)",
        len(results), data.get("total_count"), data.get("cursor"),
    )
    if not results and data.get("total_count"):
        logger.warning(
            "total_count=%s but 0 listings parsed - response shape may not match "
            "what normalize_listing expects. Raw keys: %s",
            data.get("total_count"), list(data.keys()),
        )
    return results


def get_listing_details(listing_id: str) -> dict:
    """More expensive full-listing endpoint (includes description).
    Only call this for listings that passed Stage 1 filtering."""
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

    return response.json()


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
        "category": raw.get("category"),
        "is_live": raw.get("is_live"),
        "is_sold": raw.get("is_sold"),
        # Opportunistic - present in the docs' example search response,
        # though earlier testing found it null. Capture it for free
        # when it's there; Stage 2's item lookup remains the reliable
        # fallback for the listing_created_at histogram.
        "listed_at": raw.get("listed_at"),
    }
