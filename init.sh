#!/usr/bin/env bash
# One-time local setup: creates .venv, installs dependencies, collects your
# Notion credentials into .env, and walks through config.yml (site title,
# base_path, etc.). After this, use ./build_local.sh any time you want to
# preview the site.
set -euo pipefail
cd "$(dirname "$0")"

cat <<'EOF'
Setting up notion2github.

Step-by-step guides with screenshots, if you'd like to follow along:
  Notion setup:  https://fisher98kim.github.io/notion2github/posts/how-to-set-up-notion/
  GitHub setup:  https://fisher98kim.github.io/notion2github/posts/how-to-set-up-github/

EOF

if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
echo "Installing dependencies..."
pip install -q -r requirements.txt

if [ -f .env ]; then
  echo ".env already exists — leaving it as is."
else
  echo
  echo "Now let's set up your Notion credentials (see README section 1 if you don't have these yet)."
  read -rsp "NOTION_TOKEN (input hidden): " notion_token
  echo
  read -rp "NOTION_DATABASE_ID: " notion_database_id
  cat >.env <<EOF
NOTION_TOKEN=$notion_token
NOTION_DATABASE_ID=$notion_database_id
EOF
  echo ".env created."
fi

# --- config.yml ---
# Reads/writes the simple "  key: value" lines in config.yml, which is safe
# for this file's flat structure and keeps the existing comments intact.
get_config() {
  python3 - "$1" <<'PYEOF'
import re, sys
key = sys.argv[1]
with open("config.yml") as f:
    content = f.read()
m = re.search(r'^  ' + re.escape(key) + r': *"?([^"\n]*)"?', content, re.MULTILINE)
print(m.group(1) if m else "")
PYEOF
}

set_config() {
  python3 - "$1" "$2" <<'PYEOF'
import re, sys
key, value = sys.argv[1], sys.argv[2]
with open("config.yml") as f:
    content = f.read()
escaped = value.replace('\\', '\\\\').replace('"', '\\"')
pattern = re.compile(r'^(  ' + re.escape(key) + r':).*$', re.MULTILINE)
content, n = pattern.subn(r'\1 "' + escaped + '"', content, count=1)
if n:
    with open("config.yml", "w") as f:
        f.write(content)
PYEOF
}

# Suggest base_path from the git remote: <owner>.github.io -> "" (user/org
# page), anything else -> "/repo-name" (project page). This is the value
# people most often get wrong, so default it instead of asking cold.
have_suggestion="false"
suggested_base_path=""
suggested_github_url=""
remote_url=$(git remote get-url origin 2>/dev/null || true)
if [ -n "$remote_url" ]; then
  read -r have_suggestion suggested_base_path suggested_github_url <<<"$(python3 - "$remote_url" <<'PYEOF'
import re, sys
url = sys.argv[1]
m = re.search(r'[:/]([^/]+)/([^/]+?)(\.git)?/?$', url)
if m:
    owner, repo = m.group(1), m.group(2)
    base_path = "" if repo.lower() == f"{owner.lower()}.github.io" else f"/{repo}"
    print("true", base_path if base_path else "-", f"https://github.com/{owner}")
else:
    print("false - -")
PYEOF
)"
  [ "$suggested_base_path" = "-" ] && suggested_base_path=""
  [ "$suggested_github_url" = "-" ] && suggested_github_url=""
fi

prompt_config() {
  # $4 = "true" to prefer fallback_default over the value already in
  # config.yml (used for base_path/github_url, which are re-derived from the
  # git remote each run and should win over a stale/example value).
  local key="$1" label="$2" fallback_default="$3" prefer_fallback="${4:-false}" current default input
  current=$(get_config "$key")
  if [ "$prefer_fallback" = "true" ] && [ "$have_suggestion" = "true" ]; then
    default="$fallback_default"
  else
    default="${current:-$fallback_default}"
  fi
  read -rp "$label [$default]: " input
  set_config "$key" "${input:-$default}"
}

echo
echo "Now let's fill in config.yml (site title, links — this file is committed, no secrets go here)."
prompt_config "title" "Site title" "My Blog"
prompt_config "base_path" "base_path (\"/repo-name\" for a project page, \"\" for username.github.io)" "$suggested_base_path" true
prompt_config "tagline" "Tagline (optional)" ""
prompt_config "github_url" "GitHub URL (optional)" "$suggested_github_url" true
prompt_config "email" "Contact email (optional)" ""
echo "config.yml updated."

echo
echo "Setup complete. Run ./build_local.sh any time to preview the site at http://localhost:8000."
