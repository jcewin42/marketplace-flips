"""Thin wrapper around the SociaVault Marketplace API.
"""
import requests

from config import SOCIAVAULT_API_KEY

BASE_URL = "https://api.sociavault.com"


def search_marketplace(query: str, latitude: float, longitude: float, radius: int) -> list:
    """Cheap search endpoint. Returns a list of raw listing dicts."""
    response = requests.get(
        f"{BASE_URL}/v1/scrape/facebook-marketplace/search", 
        headers={"X-API-Key": SOCIAVAULT_API_KEY},
        params={"query": query, "lat": latitude, "lng": longitude, "radius_km": radius, "sort_by": "creation_time_descend"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json().get("results", [])


def get_listing_details(listing_id: str) -> dict:
    """More expensive full-listing endpoint (includes description).
    Only call this for listings that passed Stage 1 filtering."""
    response = requests.get(
        f"{BASE_URL}/marketplace/listing/{listing_id}",  # TODO: confirm real path
        headers={"Authorization": f"Bearer {SOCIAVAULT_API_KEY}"},
        timeout=15,
    )
    response.raise_for_status()
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
