"""Thin wrapper around the Notion API for fetching blog posts."""

from notion_client import Client


def get_client(token: str) -> Client:
    return Client(auth=token)


def get_data_source_id(client: Client, database_id: str) -> str:
    """Databases hold their queryable schema in a data source (Notion API 2025-09-03+)."""
    database = client.databases.retrieve(database_id=database_id)
    return database["data_sources"][0]["id"]


def fetch_published_posts(client: Client, database_id: str) -> list[dict]:
    """Return all pages in the database whose Status is Publish, newest first."""
    data_source_id = get_data_source_id(client, database_id)
    posts: list[dict] = []
    cursor = None
    while True:
        kwargs = dict(
            data_source_id=data_source_id,
            filter={"property": "Status", "status": {"equals": "Publish"}},
            sorts=[{"property": "Date", "direction": "descending"}],
        )
        if cursor:
            kwargs["start_cursor"] = cursor
        response = client.data_sources.query(**kwargs)
        posts.extend(response["results"])
        if not response.get("has_more"):
            break
        cursor = response["next_cursor"]
    return posts


def fetch_tag_order(client: Client, database_id: str, property_name: str = "Tag") -> list[str]:
    """Return multi-select option names in the order defined on the Notion property
    (the order you see/drag in Notion's "Edit property" panel)."""
    data_source_id = get_data_source_id(client, database_id)
    data_source = client.data_sources.retrieve(data_source_id=data_source_id)
    prop = data_source["properties"].get(property_name)
    if not prop or prop["type"] != "multi_select":
        return []
    return [option["name"] for option in prop["multi_select"]["options"]]


def fetch_all_blocks(client: Client, block_id: str) -> list[dict]:
    """Recursively fetch all child blocks of a page/block, depth-first."""
    blocks: list[dict] = []
    cursor = None
    while True:
        kwargs = {"block_id": block_id}
        if cursor:
            kwargs["start_cursor"] = cursor
        response = client.blocks.children.list(**kwargs)
        for block in response["results"]:
            if block.get("has_children") and block["type"] != "child_page":
                block["_children"] = fetch_all_blocks(client, block["id"])
            blocks.append(block)
        if not response.get("has_more"):
            break
        cursor = response["next_cursor"]
    return blocks
