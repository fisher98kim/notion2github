"""Loads the site's config.yml (non-secret settings) into a plain dict."""

from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yml"

_PLACEHOLDER_DATABASE_ID = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise SystemExit(f"config.yml not found at {CONFIG_PATH}. Copy config.yml and fill it in.")

    with CONFIG_PATH.open(encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    database_id = (config.get("notion") or {}).get("database_id", "")
    if not database_id or database_id == _PLACEHOLDER_DATABASE_ID:
        raise SystemExit("config.yml: notion.database_id is not set. Edit config.yml first.")

    return config
