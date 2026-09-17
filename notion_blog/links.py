"""Rewrites links to sibling pages in the same Notion database into
internal blog links, instead of leaving them pointing back at Notion."""

import re

_PAGE_ID_RE = re.compile(r"([0-9a-f]{32})(?:[?#]|$)", re.IGNORECASE)


def extract_page_id(url: str) -> str | None:
    """Pull the bare 32-character page ID out of a Notion URL, ignoring
    dashes and whatever title slug or query string surrounds it."""
    compact = url.replace("-", "")
    match = _PAGE_ID_RE.search(compact)
    return match.group(1).lower() if match else None


def linkify_internal_pages(
    blocks: list[dict], page_id_to_path: dict[str, str], base_path: str
) -> list[dict]:
    for block in blocks:
        for rich_text in _rich_text_lists(block):
            for rt in rich_text:
                href = rt.get("href")
                page_id = extract_page_id(href) if href else None
                target = page_id_to_path.get(page_id) if page_id else None
                if target:
                    rt["href"] = f"{base_path}/{target}/"
        if block.get("_children"):
            linkify_internal_pages(block["_children"], page_id_to_path, base_path)
    return blocks


def _rich_text_lists(block: dict):
    """Yield every rich-text list a block carries (most block types keep
    one under their own key; table rows keep one per cell instead)."""
    btype = block["type"]
    data = block.get(btype, {})
    if "rich_text" in data:
        yield data["rich_text"]
    if btype == "table_row":
        yield from data.get("cells", [])
