"""Downloads Notion-hosted files (images, PDFs, attachments) so they survive
the S3 URL expiry (~1 hour) instead of breaking on the published site."""

import hashlib
from pathlib import Path
from urllib.parse import urlparse

import requests

_FILE_BLOCK_TYPES = ("image", "pdf", "file")


def localize_images(blocks: list[dict], uploads_dir: Path, slug: str) -> list[dict]:
    """Downloads each file block's image and rewrites it to a root-relative
    /static/uploads/... URL. Deliberately base_path-free: the result is cached
    across builds (see cache.py), and a build's base_path can vary (local
    preview vs. a subpath-deployed production build) — apply_base_path()
    below applies that prefix fresh on every build instead."""
    uploads_dir.mkdir(parents=True, exist_ok=True)
    for block in blocks:
        btype = block["type"]
        if btype in _FILE_BLOCK_TYPES and block[btype].get("type") == "file":
            url = block[btype]["file"]["url"]
            filename = _download(url, uploads_dir, slug)
            localized = {
                "type": "external",
                "external": {"url": f"/static/uploads/{filename}"},
                "caption": block[btype].get("caption", []),
            }
            if "name" in block[btype]:
                localized["name"] = block[btype]["name"]
            block[btype] = localized
        if block.get("_children"):
            block["_children"] = localize_images(block["_children"], uploads_dir, slug)
    return blocks


def apply_base_path(blocks: list[dict], base_path: str) -> list[dict]:
    """Prefixes the root-relative /static/uploads/... URLs localize_images
    produces with the site's base_path. A separate, cheap pass so cached
    blocks stay base_path-agnostic (see localize_images's docstring)."""
    if base_path:
        for block in blocks:
            data = block.get(block["type"])
            if isinstance(data, dict) and data.get("type") == "external":
                url = data["external"]["url"]
                if url.startswith("/static/uploads/"):
                    data["external"]["url"] = base_path + url
            if block.get("_children"):
                apply_base_path(block["_children"], base_path)
    return blocks


def _download(url: str, uploads_dir: Path, slug: str) -> str:
    # Notion's file URLs are freshly presigned on every request, so the URL
    # itself isn't a stable cache key even when the underlying file is
    # unchanged. Hash the downloaded bytes instead, so re-syncing an
    # untouched post doesn't produce a new filename (and a noisy diff)
    # every time.
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    ext = Path(urlparse(url).path).suffix or ".bin"
    digest = hashlib.md5(response.content).hexdigest()[:10]
    filename = f"{slug}-{digest}{ext}"
    dest = uploads_dir / filename
    if not dest.exists():
        dest.write_bytes(response.content)
    return filename
