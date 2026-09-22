"""Converts Notion database properties and blocks into plain data / HTML."""

import re
from html import escape


# ---- Page properties -------------------------------------------------

def _find_property(page: dict, prop_name: str) -> dict | None:
    """Notion property names are case-sensitive to the API but people
    don't type them consistently, so match case-insensitively."""
    props = page["properties"]
    if prop_name in props:
        return props[prop_name]
    lname = prop_name.lower()
    for key, value in props.items():
        if key.lower() == lname:
            return value
    return None


def get_title(page: dict, prop_name: str = "Title") -> str:
    prop = _find_property(page, prop_name)
    return "".join(t["plain_text"] for t in prop["title"]).strip()


def get_rich_text(page: dict, prop_name: str) -> str:
    prop = _find_property(page, prop_name)
    if not prop or not prop.get("rich_text"):
        return ""
    return "".join(t["plain_text"] for t in prop["rich_text"]).strip()


def get_select(page: dict, prop_name: str) -> str | None:
    prop = _find_property(page, prop_name)
    if not prop or not prop.get("select"):
        return None
    return prop["select"]["name"]


def get_multi_select(page: dict, prop_name: str) -> list[str]:
    prop = _find_property(page, prop_name)
    if not prop:
        return []
    return [o["name"] for o in prop.get("multi_select", [])]


def get_date(page: dict, prop_name: str) -> str:
    prop = _find_property(page, prop_name)
    if not prop or not prop.get("date"):
        return ""
    return prop["date"]["start"]


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-") or "post"


# ---- Rich text -> inline HTML ----------------------------------------

def rich_text_to_html(rich_text_list: list[dict]) -> str:
    parts = []
    for rt in rich_text_list:
        if rt.get("type") == "equation":
            expr = rt["equation"]["expression"]
            parts.append(f'<span class="math-inline">\\({escape(expr)}\\)</span>')
            continue
        text = escape(rt["plain_text"]).replace("\n", "<br>")
        annotations = rt.get("annotations", {})
        if annotations.get("code"):
            text = f"<code>{text}</code>"
        if annotations.get("bold"):
            text = f"<strong>{text}</strong>"
        if annotations.get("italic"):
            text = f"<em>{text}</em>"
        if annotations.get("strikethrough"):
            text = f"<s>{text}</s>"
        if annotations.get("underline"):
            text = f"<u>{text}</u>"
        href = rt.get("href")
        if href:
            text = f'<a href="{escape(href)}">{text}</a>'
        parts.append(text)
    return "".join(parts)


# ---- Blocks -> HTML ----------------------------------------------------

_LIST_TYPES = {
    "bulleted_list_item": "ul",
    "numbered_list_item": "ol",
}

# Block types whose own renderer already consumes _children (list items fold
# theirs in via _render_list_item in the loop below; toggle and table handle
# theirs inside _render_block). Every other block type can carry indented
# sub-blocks too (Notion lets you Tab-indent under a paragraph, heading, ...)
# and blocks_to_html must render those explicitly or they're silently dropped.
_SELF_RENDERS_CHILDREN = {"toggle", "table", *_LIST_TYPES}


def blocks_to_html(blocks: list[dict]) -> str:
    html_parts = []
    i, n = 0, len(blocks)
    while i < n:
        block = blocks[i]
        btype = block["type"]
        if btype in _LIST_TYPES:
            tag = _LIST_TYPES[btype]
            items = []
            while i < n and blocks[i]["type"] == btype:
                items.append(_render_list_item(blocks[i]))
                i += 1
            html_parts.append(f"<{tag}>{''.join(items)}</{tag}>")
            continue
        html_parts.append(_render_block(block))
        if block.get("_children") and btype not in _SELF_RENDERS_CHILDREN:
            html_parts.append(f'<div class="ms-4">{blocks_to_html(block["_children"])}</div>')
        i += 1
    return "\n".join(p for p in html_parts if p)


def _render_list_item(block: dict) -> str:
    btype = block["type"]
    text = rich_text_to_html(block[btype]["rich_text"])
    inner = blocks_to_html(block["_children"]) if block.get("_children") else ""
    return f"<li>{text}{inner}</li>"


def _render_table(block: dict) -> str:
    rows = block.get("_children", [])
    has_header = block["table"].get("has_column_header", False)
    out = ["<table>"]
    for idx, row in enumerate(rows):
        cells = row["table_row"]["cells"]
        tag = "th" if (has_header and idx == 0) else "td"
        cells_html = "".join(f"<{tag}>{rich_text_to_html(c)}</{tag}>" for c in cells)
        out.append(f"<tr>{cells_html}</tr>")
    out.append("</table>")
    return "".join(out)


def _render_block(block: dict) -> str:
    btype = block["type"]
    data = block.get(btype, {})

    if btype == "paragraph":
        text = rich_text_to_html(data["rich_text"])
        return f"<p>{text}</p>" if text else ""

    if btype in ("heading_1", "heading_2", "heading_3"):
        level = btype[-1]
        text = rich_text_to_html(data["rich_text"])
        return f"<h{level}>{text}</h{level}>"

    if btype == "quote":
        return f"<blockquote>{rich_text_to_html(data['rich_text'])}</blockquote>"

    if btype == "divider":
        return "<hr>"

    if btype == "code":
        text = "".join(t["plain_text"] for t in data["rich_text"])
        lang = data.get("language", "")
        return f'<pre><code class="language-{escape(lang)}">{escape(text)}</code></pre>'

    if btype == "image":
        img = data
        url = img["file"]["url"] if img.get("type") == "file" else img["external"]["url"]
        caption = rich_text_to_html(img.get("caption", []))
        cap_html = f"<figcaption>{caption}</figcaption>" if caption else ""
        return f'<figure><img src="{escape(url)}" alt="">{cap_html}</figure>'

    if btype == "to_do":
        checked = "checked" if data.get("checked") else ""
        text = rich_text_to_html(data["rich_text"])
        return f'<div class="todo"><input type="checkbox" disabled {checked}> {text}</div>'

    if btype == "callout":
        icon = data.get("icon") or {}
        emoji = icon.get("emoji", "\U0001F4A1")
        text = rich_text_to_html(data["rich_text"])
        return f'<div class="callout"><span class="callout-icon">{emoji}</span><div>{text}</div></div>'

    if btype == "bookmark":
        url = data.get("url", "")
        return f'<a class="bookmark" href="{escape(url)}" target="_blank" rel="noopener">{escape(url)}</a>'

    if btype == "toggle":
        text = rich_text_to_html(data["rich_text"])
        inner = blocks_to_html(block.get("_children", []))
        return f"<details><summary>{text}</summary>{inner}</details>"

    if btype == "table":
        return _render_table(block)

    if btype == "equation":
        expr = data.get("expression", "")
        return f'<div class="math-block">\\[{escape(expr)}\\]</div>'

    if btype == "pdf":
        url = data["file"]["url"] if data.get("type") == "file" else data["external"]["url"]
        caption = rich_text_to_html(data.get("caption", []))
        cap_html = f"<figcaption>{caption}</figcaption>" if caption else ""
        return f'<figure><iframe class="pdf-embed" src="{escape(url)}" loading="lazy"></iframe>{cap_html}</figure>'

    if btype == "file":
        url = data["file"]["url"] if data.get("type") == "file" else data["external"]["url"]
        name = data.get("name") or "Attachment"
        return f'<a class="file-attachment" href="{escape(url)}" target="_blank" rel="noopener">\U0001F4CE {escape(name)}</a>'

    # Unsupported block types (child_page, embed, video, ...) are skipped.
    return ""
