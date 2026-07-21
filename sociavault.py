"""Thin wrapper around the SociaVault Marketplace API.

NOTE: I don't have your actual SociaVault endpoint paths/auth scheme in
front of me, so BASE_URL and the two paths below are placeholders -
swap them for what's in your SociaVault account docs/dashboard before
running this on the Pi. Everything downstream (normalize_listing) is
written against the flat dict shape, so once the request/response
plumbing is correct here, nothing else needs to change.
"""
import logging

import requests

from config import SOCIAVAULT_API_KEY

logger = logging.getLogger(__name__)

BASE_URL = "https://api.sociavault.com"


def search_marketplace(query: str, latitude: float, longitude: float, radius: int) -> list:
    """Cheap search endpoint. Returns a list of raw listing dicts."""
    url = f"{BASE_URL}/v1/scrape/facebook-marketplace/search"
    params={"query": query, "lat": latitude, "lng": longitude, "radius_km": radius, "sort_by": "creation_time_descend"},
    logger.debug("GET %s params=%s", url, params)

    response = requests.get(
        url,
        headers={"X-API-Key": SOCIAVAULT_API_KEY},
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

    results = response.json().get("results", [])
    logger.debug("SociaVault search returned %d results", len(results))
    return results


def get_listing_details(listing_id: str) -> dict:
    """More expensive full-listing endpoint (includes description).
    Only call this for listings that passed Stage 1 filtering."""
    url = f"{BASE_URL}/marketplace/listing/{listing_id}"  # TODO: confirm real path
    logger.debug("GET %s", url)

    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {SOCIAVAULT_API_KEY}"},
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
    }
