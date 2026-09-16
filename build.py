from dotenv import load_dotenv

load_dotenv()

from notion_blog.site_builder import build_site

if __name__ == "__main__":
    build_site()
