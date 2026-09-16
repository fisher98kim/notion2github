# notion2github

A template that turns a Notion database into a static HTML blog deployed on GitHub Pages.
Fill in `config.yml`, and GitHub Actions keeps the site in sync automatically.

## 0. Start from this template

Pick whichever of these you're comfortable with — they all end up in the same place: your own repo with this code in it.

**Option A — Use this template (recommended if you're on GitHub's website)**
Click **Use this template** → **Create a new repository** at the top of this repo's GitHub page. This gives you an independent repo (no "forked from" link) with GitHub Actions already enabled by default.

**Option B — Fork**
Click **Fork** at the top of this repo's GitHub page. Simplest click, but GitHub disables Actions on forks by default — after forking, go to your fork's **Actions** tab and click the button to enable workflows (and note that the scheduled/cron run is less reliable on forks than on an independent repo).

**Option C — Clone it yourself (no GitHub UI needed)**
If you'd rather work from the terminal, first create an empty repo on GitHub named `<your-username>.github.io` (or any name, for a project page), then:

```bash
git clone --depth 1 https://github.com/fisher98kim/notion2github.git <your-username>.github.io
cd <your-username>.github.io
rm -rf .git && git init
git remote add origin https://github.com/<your-username>/<your-username>.github.io.git
git add -A && git commit -m "Initial commit from notion2github"
git branch -M main
git push -u origin main
```

`rm -rf .git` matters here — without it you'd drag this template's commit history (and its original author) into your own repo. Since this creates a plain repo with no fork relationship, Actions works the same as Option A (enabled by default, no extra steps).

## 1. Set up Notion

1. Go to https://www.notion.so/my-integrations → **New integration** → give it any name → pick your workspace → create it.
2. Copy the **Internal Integration Secret** it generates. (`NOTION_TOKEN`)
3. In Notion, create a new **database (table)** with these properties:

   | Property name | Type | Description |
   |---|---|---|
   | Title | Title (built in) | Post title |
   | Status | Status | Options: `Draft`, `Publish` — only `Publish` posts show up on the site |
   | Date | Date | Publish date, used for sorting |
   | Slug | Text | (optional) URL slug. Auto-generated from the title if left blank. Set it to `about` to make that page your profile/About page instead of a regular post |
   | Tag | Multi-select | (optional) |
   | Summary | Text | (optional) Shown in the post list |

4. On the database page, click `···` (top right) → **Connections** → connect the integration you just created. (Without this, the API only ever returns an empty list.)
5. Open the database in your browser and copy the 32-character ID from the URL. (`NOTION_DATABASE_ID`)
   In `https://www.notion.so/xxxx/1a2b3c...32 chars...?v=...`, it's the `1a2b3c...` part.

## 2. Fill in config.yml

Open `config.yml` at the repo root. **This file gets committed to the repo, so no secrets go here** — those (`NOTION_TOKEN`, `NOTION_DATABASE_ID`) are registered separately in step 3 below.

```yaml
site:
  title: "My Blog"
  base_path: ""        # "/repo-name" for username.github.io/repo-name, "" for username.github.io
  tagline: ""
  avatar: ""
  github_url: ""
  email: ""

deploy:
  auto_sync: true       # set to false to disable automatic syncing (manual runs still work)
```

## 3. Configure the GitHub repository

1. Register the secrets. With the [GitHub CLI](https://cli.github.com/) installed and logged in (`gh auth login`), run these from the repo folder:

   ```bash
   gh secret set NOTION_TOKEN
   gh secret set NOTION_DATABASE_ID
   ```

   Each prompts you to paste the value. No CLI? Go to **Settings → Secrets and variables → Actions → Secrets → New repository secret** and add both `NOTION_TOKEN` and `NOTION_DATABASE_ID` there instead.
2. Go to **Settings → Pages** → Source: `Deploy from a branch` → Branch: `main`, folder: `/docs` → Save.
3. Go to the **Actions** tab → select the `Build and Deploy Blog` workflow → **Run workflow** to trigger the first build manually.

## 4. Automatic syncing

`.github/workflows/build.yml` does the following:

- Runs on an hourly cron schedule and on every push to `main`. If `deploy.auto_sync` in `config.yml` is `false`, these automatic runs are skipped.
- Manually running it from the Actions tab (**Run workflow**) always works, regardless of the `auto_sync` setting.
- Fetches every `Publish`-status post from Notion, regenerates `docs/`, and commits & pushes it if anything changed — which triggers a GitHub Pages redeploy.

In short: write a post in Notion, flip its Status to `Publish`, and it shows up on your blog within the hour.

If you'd rather not run any automation, set `auto_sync` to `false` in `config.yml` and build/push locally instead (see below).

## 5. Build and test locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in NOTION_TOKEN and NOTION_DATABASE_ID
python build.py
python -m http.server --directory docs 8000   # check http://localhost:8000
```

## Project structure

```
config.yml            # site config (title, sidebar info, auto_sync)
notion_blog/
  config.py            # loads config.yml
  notion_api.py        # Notion API calls (database query, recursive block fetch)
  renderer.py           # Notion blocks/properties -> HTML
  images.py             # localizes Notion-hosted files (their URLs expire)
  site_builder.py        # orchestrates the whole build
templates/               # Jinja2 templates (base/index/post/about)
static/style.css         # site styles
docs/                     # build output (served by GitHub Pages)
build.py                  # entry point: python build.py
.github/workflows/        # build & deploy automation
```

## Supported Notion blocks

Paragraphs, headings (H1-H3), bulleted/numbered lists (including nesting), quotes, dividers, code, images, to-dos, callouts, bookmarks, toggles, tables, PDFs, file attachments. Other block types (embeds, equation blocks) are skipped.
