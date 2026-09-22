"""Persists each page's fetched-and-localized blocks across builds, keyed by
its Notion last_edited_time (confirmed to bump on content edits, not just
property changes). An unedited post reuses its cached blocks instead of
re-fetching from Notion and re-downloading its images.

Cached blocks are stored in the canonical, base_path-free form localize_images
produces (root-relative /static/uploads/... URLs, original Notion hrefs) so
the same cache is valid for both a local preview build and a subpath-deployed
production build; site_builder applies base_path and sibling-page linkification
fresh on every build, cache hit or not.
"""

import json
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent / ".notion_cache"
MANIFEST_PATH = CACHE_DIR / "manifest.json"
UPLOADS_DIR = CACHE_DIR / "uploads"


def load() -> dict:
    if not MANIFEST_PATH.exists():
        return {}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def save(manifest: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_blocks(manifest: dict, page_id: str, last_edited_time: str) -> list[dict] | None:
    entry = manifest.get(page_id)
    if entry and entry.get("last_edited_time") == last_edited_time:
        return entry["blocks"]
    return None


def set_blocks(manifest: dict, page_id: str, last_edited_time: str, blocks: list[dict]) -> None:
    manifest[page_id] = {"last_edited_time": last_edited_time, "blocks": blocks}
