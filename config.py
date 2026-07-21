"""Loads the active search configuration based on the ACTIVE_SEARCH
environment variable.

To add a new search (e.g. lawn mowers), drop a new module in
search_configs/ that defines a module-level CONFIG = SearchConfig(...),
then set ACTIVE_SEARCH to that module's filename (no .py). Nothing else
in the codebase needs to change - monitor.py, db.py, etc. are all
written against SearchConfig, never against a specific search.
"""
import importlib
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class SearchConfig:
    name: str
    query: str
    latitude: float
    longitude: float
    radius: int
    database_path: str
    negative_keywords: list = field(default_factory=list)
    schedule: str = "default"  # reserved for future per-search schedules


def load_active_config() -> SearchConfig:
    active_search = os.environ.get("ACTIVE_SEARCH", "outboard_motors")
    module = importlib.import_module(f"search_configs.{active_search}")
    return module.CONFIG


DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
SOCIAVAULT_API_KEY = os.environ.get("SOCIAVAULT_API_KEY")
