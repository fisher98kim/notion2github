"""Orchestrates: fetch posts from Notion -> render -> write static site to docs/."""

import os
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from . import notion_api
from .config import load_config
from .images import localize_images
from .renderer import (
    blocks_to_html,
    get_date,
    get_multi_select,
    get_rich_text,
    get_title,
    slugify,
)

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
OUTPUT_DIR = ROOT / "docs"

# A post whose Slug property is exactly this becomes the profile page at
# /about/ (linked from the site title) instead of a regular blog post.
ABOUT_SLUG = "about"


def build_site() -> None:
    config = load_config()
    token = os.environ["NOTION_TOKEN"]
    database_id = os.environ["NOTION_DATABASE_ID"]

    site = config.get("site") or {}
    site_title = site.get("title") or "My Notion Blog"
    base_path = (site.get("base_path") or "").rstrip("/")

    profile_context = {
        "tagline": site.get("tagline") or "",
        "avatar": site.get("avatar") or "",
        "github_url": site.get("github_url") or "",
        "email": site.get("email") or "",
    }

    client = notion_api.get_client(token)
    pages = notion_api.fetch_published_posts(client, database_id)
    tag_order = notion_api.fetch_tag_order(client, database_id)

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    post_template = env.get_template("post.html")
    index_template = env.get_template("index.html")
    about_template = env.get_template("about.html")

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    (OUTPUT_DIR / ".nojekyll").touch()
    shutil.copytree(STATIC_DIR, OUTPUT_DIR / "static")

    posts_meta = []
    posts_content = {}
    about_page = None
    for page in pages:
        title = get_title(page)
        raw_slug = get_rich_text(page, "Slug")
        slug = raw_slug or slugify(title)
        date = get_date(page, "Date")
        tags = [{"name": t, "slug": slugify(t)} for t in get_multi_select(page, "Tag")]
        summary = get_rich_text(page, "Summary")

        blocks = notion_api.fetch_all_blocks(client, page["id"])
        blocks = localize_images(blocks, OUTPUT_DIR / "static" / "uploads", slug, base_path)
        content_html = blocks_to_html(blocks)

        if raw_slug.strip().lower() == ABOUT_SLUG:
            about_page = {"title": title, "content": content_html}
            continue

        posts_content[slug] = content_html
        posts_meta.append(
            {"title": title, "slug": slug, "date": date, "tags": tags, "summary": summary}
        )

    posts_meta.sort(key=lambda p: p["date"], reverse=True)

    categories = _build_categories(posts_meta, tag_order)

    for post in posts_meta:
        post_dir = OUTPUT_DIR / "posts" / post["slug"]
        post_dir.mkdir(parents=True, exist_ok=True)
        html = post_template.render(
            site_title=site_title,
            base_path=base_path,
            categories=categories,
            title=post["title"],
            date=post["date"],
            tags=post["tags"],
            content=posts_content[post["slug"]],
            **profile_context,
        )
        (post_dir / "index.html").write_text(html, encoding="utf-8")

    index_html = index_template.render(
        site_title=site_title,
        base_path=base_path,
        posts=posts_meta,
        categories=categories,
        **profile_context,
    )
    (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")

    for category in categories:
        tag_dir = OUTPUT_DIR / "tags" / category["slug"]
        tag_dir.mkdir(parents=True, exist_ok=True)
        tag_html = index_template.render(
            site_title=site_title,
            base_path=base_path,
            posts=category["posts"],
            categories=categories,
            category=category,
            **profile_context,
        )
        (tag_dir / "index.html").write_text(tag_html, encoding="utf-8")

    if about_page:
        about_dir = OUTPUT_DIR / "about"
        about_dir.mkdir(parents=True, exist_ok=True)
        about_html = about_template.render(
            site_title=site_title,
            base_path=base_path,
            categories=categories,
            is_about=True,
            title=about_page["title"],
            content=about_page["content"],
            **profile_context,
        )
        (about_dir / "index.html").write_text(about_html, encoding="utf-8")

    print(
        f"Built {len(posts_meta)} post(s), {len(categories)} categor(ies), "
        f"about page: {bool(about_page)} -> {OUTPUT_DIR}"
    )


def _build_categories(posts_meta: list[dict], tag_order: list[str]) -> list[dict]:
    by_slug: dict[str, dict] = {}
    for post in posts_meta:
        for tag in post["tags"]:
            entry = by_slug.setdefault(
                tag["slug"], {"name": tag["name"], "slug": tag["slug"], "posts": []}
            )
            entry["posts"].append(post)
    for entry in by_slug.values():
        entry["count"] = len(entry["posts"])
    order_index = {slugify(name): i for i, name in enumerate(tag_order)}
    return sorted(by_slug.values(), key=lambda c: order_index.get(c["slug"], len(order_index)))


if __name__ == "__main__":
    build_site()
