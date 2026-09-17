import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()

from notion_blog.site_builder import build_site

if __name__ == "__main__":
    local = "--local" in sys.argv
    build_site(local=local)
    if local:
        print("Serving docs/ at http://localhost:8000 (Ctrl+C to stop)")
        subprocess.run([sys.executable, "-m", "http.server", "--directory", "docs", "8000"])
