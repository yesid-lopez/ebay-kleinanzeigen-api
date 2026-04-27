# Kleinanzeigen MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that wraps the Kleinanzeigen scraper API. Add it to any Cursor project to let AI agents search and browse Kleinanzeigen listings.

The server is a single Python script with inline dependencies — no install step needed, just `uv`.

## Tools

| Tool | Description |
|------|-------------|
| `search_listings` | Search listings by keyword, location, price range, and radius |
| `get_listing` | Fetch full details for a single listing by ID |
| `search_listings_detailed` | Search + fetch details for every result in one call |

## Setup

### Prerequisites

- [uv](https://docs.astral.sh/uv/) installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Add to Cursor

Add the following to your project's `.cursor/mcp.json` (or the global config at `~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "kleinanzeigen": {
      "command": "uv",
      "args": ["run", "/absolute/path/to/ebay/mcp/server.py"],
      "env": {
        "KLEINANZEIGEN_API_URL": "http://192.168.2.100:80"
      }
    }
  }
}
```

Replace `/absolute/path/to/ebay` with the actual path on your machine.

> The `KLEINANZEIGEN_API_URL` env var is optional — it defaults to `http://192.168.2.100:80`.

### Run manually (for testing)

```sh
uv run mcp/server.py
```

Or use the MCP dev inspector:

```sh
uv run mcp dev mcp/server.py
```

## Tool Reference

### search_listings

Search for listings with optional filters.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | no | Search term, e.g. "fahrrad" |
| `location` | string | no | City or postal code, e.g. "10178" |
| `radius` | integer | no | Radius in km |
| `min_price` | integer | no | Min price in EUR |
| `max_price` | integer | no | Max price in EUR |
| `page_count` | integer | no | Pages to fetch (1-20, default 1) |

### get_listing

Fetch details for one listing.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | yes | The listing/ad ID |

### search_listings_detailed

Search + fetch full details. Slower but returns complete data.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | no | Search term |
| `location` | string | no | City or postal code |
| `radius` | integer | no | Radius in km |
| `min_price` | integer | no | Min price in EUR |
| `max_price` | integer | no | Max price in EUR |
| `page_count` | integer | no | Pages (1-3, default 1) |
| `max_concurrent_details` | integer | no | Concurrent fetches (1-10, default 5) |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KLEINANZEIGEN_API_URL` | `http://192.168.2.100:80` | Base URL of the Kleinanzeigen API |
