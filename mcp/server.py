# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mcp[cli]",
#     "httpx",
# ]
# ///

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = os.environ.get("KLEINANZEIGEN_API_URL", "http://192.168.2.100:80")

mcp = FastMCP(
    "kleinanzeigen",
    instructions=(
        "This server exposes the Kleinanzeigen (eBay Kleinanzeigen) scraper API.\n"
        "Use 'search_listings' to find listings by keyword, location, price, etc.\n"
        "Use 'get_listing' to fetch full details for a single listing by its ID.\n"
        "Use 'search_listings_detailed' to search AND fetch details in one call."
    ),
)

_client = httpx.AsyncClient(base_url=API_BASE, timeout=60)


async def _api_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    cleaned = {k: v for k, v in (params or {}).items() if v is not None}
    resp = await _client.get(path, params=cleaned)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
async def search_listings(
    query: str | None = None,
    location: str | None = None,
    radius: int | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    page_count: int | None = None,
) -> dict[str, Any]:
    """Search Kleinanzeigen listings by keyword, location, price range, and radius.

    Returns a list of matching listings with basic info (title, price, location, ad ID).

    Args:
        query: Search term, e.g. "fahrrad"
        location: City name or postal code, e.g. "10178" or "Berlin"
        radius: Search radius in km from the location
        min_price: Minimum price in EUR
        max_price: Maximum price in EUR
        page_count: Number of result pages to fetch (1-20, default 1)
    """
    return await _api_get(
        "/inserate",
        {
            "query": query,
            "location": location,
            "radius": radius,
            "min_price": min_price,
            "max_price": max_price,
            "page_count": page_count,
        },
    )


@mcp.tool()
async def get_listing(id: str) -> dict[str, Any]:
    """Fetch detailed information for a single Kleinanzeigen listing.

    Returns description, seller info, location, pricing, images, and metadata.

    Args:
        id: The listing (ad) ID to fetch details for
    """
    return await _api_get(f"/inserat/{id}")


@mcp.tool()
async def search_listings_detailed(
    query: str | None = None,
    location: str | None = None,
    radius: int | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    page_count: int | None = None,
    max_concurrent_details: int | None = None,
) -> dict[str, Any]:
    """Search Kleinanzeigen listings AND fetch full details for each result in one call.

    Slower than search_listings but returns complete information.
    Use when you need descriptions, seller info, or images for every result.

    Args:
        query: Search term
        location: City name or postal code
        radius: Search radius in km
        min_price: Minimum price in EUR
        max_price: Maximum price in EUR
        page_count: Pages to fetch (1-3, default 1). Lower max due to detail fetching.
        max_concurrent_details: Max concurrent detail fetches (1-10, default 5)
    """
    return await _api_get(
        "/inserate-detailed",
        {
            "query": query,
            "location": location,
            "radius": radius,
            "min_price": min_price,
            "max_price": max_price,
            "page_count": page_count,
            "max_concurrent_details": max_concurrent_details,
        },
    )


if __name__ == "__main__":
    mcp.run()
