#!/usr/bin/env bash
# One-time local setup: creates .venv, installs dependencies, and collects
# your Notion credentials into .env. After this, use ./build_local.sh
# any time you want to preview the site.
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

echo
echo "Setup complete. Run ./build_local.sh any time to preview the site at http://localhost:8000."
