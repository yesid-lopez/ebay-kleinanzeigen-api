# Kleinanzeigen MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that wraps the Kleinanzeigen scraper API. Add it to any Cursor project to let AI agents search and browse Kleinanzeigen listings.

## Tools

| Tool | Description |
|------|-------------|
| `search_listings` | Search listings by keyword, location, price range, and radius |
| `get_listing` | Fetch full details for a single listing by ID |
| `search_listings_detailed` | Search + fetch details for every result in one call |

## Setup (Remote)

The MCP server runs as an HTTP service on `192.168.2.100:8080`. Any Cursor project can connect to it with zero dependencies.

Add the following to your project's `.cursor/mcp.json` (or `~/.cursor/mcp.json` for global access):

```json
{
  "mcpServers": {
    "kleinanzeigen": {
      "url": "http://192.168.2.100:8080/mcp"
    }
  }
}
```

That's it -- no local clone, no installs.

## Setup (Local / Dev)

For local development or if you prefer running the server as a subprocess:

### Prerequisites

- [uv](https://docs.astral.sh/uv/) installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Add to Cursor

```json
{
  "mcpServers": {
    "kleinanzeigen": {
      "command": "uv",
      "args": ["run", "/absolute/path/to/ebay/mcp/server.py"],
      "env": {
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

Replace `/absolute/path/to/ebay` with the actual path on your machine.

### Run manually

```sh
# Remote HTTP mode (default)
uv run mcp/server.py

# Local stdio mode
MCP_TRANSPORT=stdio uv run mcp/server.py

# Dev inspector
uv run mcp dev mcp/server.py
```

## Deployment

### Docker

```sh
cd mcp
docker build -t kleinanzeigen-mcp .
docker run -d -p 8080:8080 \
  -e KLEINANZEIGEN_API_URL=http://192.168.2.100:80 \
  kleinanzeigen-mcp
```

### Docker Compose (alongside the scraper API)

```yaml
services:
  mcp:
    build: ./mcp
    ports:
      - "8080:8080"
    environment:
      - KLEINANZEIGEN_API_URL=http://api:8000
    depends_on:
      - api

  api:
    build: .
    ports:
      - "80:8000"
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
| `MCP_TRANSPORT` | `streamable-http` | Transport mode: `streamable-http` for remote, `stdio` for local |
