"""Orchestrates: fetch posts from Notion -> render -> write static site to docs/."""

import copy
import os
import shutil
import subprocess
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from . import cache, notion_api
from .config import load_config
from .images import apply_base_path, localize_images
from .links import linkify_internal_pages
from .renderer import (
    blocks_to_html,
    get_date,
    get_multi_select,
    get_rich_text,
    get_select,
    get_title,
    slugify,
)

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
OUTPUT_DIR = ROOT / "docs"

# A post whose title is exactly this becomes the profile page at /about/
# (linked from the site title) instead of a regular blog post.
ABOUT_TITLE = "about"


def build_site(local: bool = False) -> None:
    config = load_config()
    token = os.environ["NOTION_TOKEN"]
    database_id = os.environ["NOTION_DATABASE_ID"]

    site = config.get("site") or {}
    site_title = site.get("title") or "My Notion Blog"
    # base_path is only meaningful once the site is deployed under a
    # subpath (a GitHub Pages project page); a local preview is always
    # served from "/", so config.yml's value would break every link.
    base_path = "" if local else (site.get("base_path") or "").rstrip("/")

    profile_context = {
        "tagline": site.get("tagline") or "",
        "avatar": site.get("avatar") or "",
        "github_url": site.get("github_url") or "",
        "email": site.get("email") or "",
    }

    client = notion_api.get_client(token)
    pages = notion_api.fetch_published_posts(client, database_id)
    tag_order = notion_api.fetch_option_order(client, database_id, "Tag", "multi_select")
    category_order = notion_api.fetch_option_order(client, database_id, "Category", "select")

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    post_template = env.get_template("post.html")
    index_template = env.get_template("index.html")
    about_template = env.get_template("about.html")

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    (OUTPUT_DIR / ".nojekyll").touch()
    shutil.copytree(STATIC_DIR, OUTPUT_DIR / "static")

    # Pass 1: cheap metadata for every page, plus a map from Notion page ID
    # to this site's own path for it. Built up front so pass 2 can rewrite
    # in-page links to sibling posts before rendering any HTML.
    page_meta = []
    page_id_to_path = {}
    for page in pages:
        title = get_title(page)
        slug = slugify(title)
        is_about = title.strip().lower() == ABOUT_TITLE
        category_name = get_select(page, "Category")
        category = {"name": category_name, "slug": slugify(category_name)} if category_name else None
        page_meta.append(
            {
                "page": page,
                "title": title,
                "slug": slug,
                "is_about": is_about,
                "date": get_date(page, "Date"),
                "category": category,
                "tags": [{"name": t, "slug": slugify(t)} for t in get_multi_select(page, "Tag")],
                "summary": get_rich_text(page, "Summary"),
            }
        )
        page_id_to_path[page["id"].replace("-", "").lower()] = (
            "about" if is_about else f"posts/{slug}"
        )

    # Pass 2: fetch each page's content and render it. Unedited pages (by
    # last_edited_time) reuse cached blocks instead of hitting Notion/S3 again.
    manifest = cache.load()
    posts_meta = []
    posts_content = {}
    about_page = None
    for meta in page_meta:
        page_id = meta["page"]["id"]
        last_edited_time = meta["page"]["last_edited_time"]
        cached_blocks = cache.get_blocks(manifest, page_id, last_edited_time)
        if cached_blocks is not None:
            blocks = copy.deepcopy(cached_blocks)
        else:
            blocks = notion_api.fetch_all_blocks(client, page_id)
            blocks = localize_images(blocks, cache.UPLOADS_DIR, meta["slug"])
            cache.set_blocks(manifest, page_id, last_edited_time, copy.deepcopy(blocks))

        blocks = apply_base_path(blocks, base_path)
        blocks = linkify_internal_pages(blocks, page_id_to_path, base_path)
        content_html = blocks_to_html(blocks)

        if meta["is_about"]:
            about_page = {"title": meta["title"], "content": content_html}
            continue

        posts_content[meta["slug"]] = content_html
        posts_meta.append(
            {k: meta[k] for k in ("title", "slug", "date", "category", "tags", "summary")}
        )

    cache.save(manifest)
    if cache.UPLOADS_DIR.exists():
        shutil.copytree(cache.UPLOADS_DIR, OUTPUT_DIR / "static" / "uploads", dirs_exist_ok=True)

    posts_meta.sort(key=lambda p: p["date"], reverse=True)

    categories = _build_categories(posts_meta, category_order)
    tag_list = _build_tags(posts_meta, tag_order)

    for post in posts_meta:
        post_dir = OUTPUT_DIR / "posts" / post["slug"]
        post_dir.mkdir(parents=True, exist_ok=True)
        html = post_template.render(
            site_title=site_title,
            base_path=base_path,
            categories=categories,
            title=post["title"],
            date=post["date"],
            category=post["category"],
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
        category_dir = OUTPUT_DIR / "categories" / category["slug"]
        category_dir.mkdir(parents=True, exist_ok=True)
        category_html = index_template.render(
            site_title=site_title,
            base_path=base_path,
            posts=category["posts"],
            categories=categories,
            category=category,
            **profile_context,
        )
        (category_dir / "index.html").write_text(category_html, encoding="utf-8")

    for tag in tag_list:
        tag_dir = OUTPUT_DIR / "tags" / tag["slug"]
        tag_dir.mkdir(parents=True, exist_ok=True)
        tag_html = index_template.render(
            site_title=site_title,
            base_path=base_path,
            posts=tag["posts"],
            categories=categories,
            tag=tag,
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
        f"Built {len(posts_meta)} post(s), {len(categories)} categor(ies), {len(tag_list)} tag(s), "
        f"about page: {bool(about_page)} -> {OUTPUT_DIR}"
    )

    subprocess.run(
        [sys.executable, "-m", "pagefind", "--site", str(OUTPUT_DIR)], check=True
    )


def _build_categories(posts_meta: list[dict], category_order: list[str]) -> list[dict]:
    """Group posts by their single Category, for the sidebar nav and /categories/ pages."""
    by_slug: dict[str, dict] = {}
    for post in posts_meta:
        category = post["category"]
        if not category:
            continue
        entry = by_slug.setdefault(
            category["slug"], {"name": category["name"], "slug": category["slug"], "posts": []}
        )
        entry["posts"].append(post)
    for entry in by_slug.values():
        entry["count"] = len(entry["posts"])
    order_index = {slugify(name): i for i, name in enumerate(category_order)}
    return sorted(by_slug.values(), key=lambda c: order_index.get(c["slug"], len(order_index)))


def _build_tags(posts_meta: list[dict], tag_order: list[str]) -> list[dict]:
    """Group posts by Tag, for the /tags/ pages (not shown in the sidebar nav)."""
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
    return sorted(by_slug.values(), key=lambda t: order_index.get(t["slug"], len(order_index)))


if __name__ == "__main__":
    build_site()
