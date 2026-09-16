"""Loads the site's config.yml (non-secret settings) into a plain dict."""

from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yml"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise SystemExit(f"config.yml not found at {CONFIG_PATH}. Copy config.yml and fill it in.")

    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
