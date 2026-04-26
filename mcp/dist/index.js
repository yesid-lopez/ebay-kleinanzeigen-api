#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod/v4";
const API_BASE = process.env.KLEINANZEIGEN_API_URL ?? "http://192.168.2.100:80";
// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
async function apiGet(path, params) {
    const url = new URL(path, API_BASE);
    if (params) {
        for (const [k, v] of Object.entries(params)) {
            if (v !== undefined && v !== "")
                url.searchParams.set(k, v);
        }
    }
    const res = await fetch(url.toString(), {
        headers: { Accept: "application/json" },
    });
    if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(`API ${res.status}: ${body || res.statusText}`);
    }
    return res.json();
}
function textResult(data) {
    return {
        content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
    };
}
// ---------------------------------------------------------------------------
// Server
// ---------------------------------------------------------------------------
const server = new McpServer({ name: "kleinanzeigen", version: "1.0.0" }, {
    capabilities: { logging: {} },
    instructions: [
        "This server exposes the Kleinanzeigen (eBay Kleinanzeigen) scraper API.",
        "Use 'search_listings' to find listings by keyword, location, price, etc.",
        "Use 'get_listing' to fetch full details for a single listing by its ID.",
        "Use 'search_listings_detailed' to search AND fetch details in one call.",
    ].join("\n"),
});
// ── Tool: search_listings ───────────────────────────────────────────────
server.registerTool("search_listings", {
    description: "Search Kleinanzeigen listings by keyword, location, price range, and radius. " +
        "Returns a list of matching listings with basic info (title, price, location, ad ID).",
    inputSchema: z.object({
        query: z.string().optional().describe("Search term, e.g. 'fahrrad'"),
        location: z
            .string()
            .optional()
            .describe("City name or postal code, e.g. '10178' or 'Berlin'"),
        radius: z
            .number()
            .int()
            .optional()
            .describe("Search radius in km from the location"),
        min_price: z
            .number()
            .int()
            .optional()
            .describe("Minimum price in EUR"),
        max_price: z
            .number()
            .int()
            .optional()
            .describe("Maximum price in EUR"),
        page_count: z
            .number()
            .int()
            .min(1)
            .max(20)
            .optional()
            .describe("Number of result pages to fetch (1-20, default 1)"),
    }),
}, async (args) => {
    const params = {};
    if (args.query)
        params.query = args.query;
    if (args.location)
        params.location = args.location;
    if (args.radius !== undefined)
        params.radius = String(args.radius);
    if (args.min_price !== undefined)
        params.min_price = String(args.min_price);
    if (args.max_price !== undefined)
        params.max_price = String(args.max_price);
    if (args.page_count !== undefined)
        params.page_count = String(args.page_count);
    const data = await apiGet("/inserate", params);
    return textResult(data);
});
// ── Tool: get_listing ───────────────────────────────────────────────────
server.registerTool("get_listing", {
    description: "Fetch detailed information for a single Kleinanzeigen listing. " +
        "Returns description, seller info, location, pricing, images, and metadata.",
    inputSchema: z.object({
        id: z.string().describe("The listing (ad) ID to fetch details for"),
    }),
}, async ({ id }) => {
    const data = await apiGet(`/inserat/${encodeURIComponent(id)}`);
    return textResult(data);
});
// ── Tool: search_listings_detailed ──────────────────────────────────────
server.registerTool("search_listings_detailed", {
    description: "Search Kleinanzeigen listings AND fetch full details for each result in one call. " +
        "Slower than search_listings but returns complete information. " +
        "Use when you need descriptions, seller info, or images for every result.",
    inputSchema: z.object({
        query: z.string().optional().describe("Search term"),
        location: z
            .string()
            .optional()
            .describe("City name or postal code"),
        radius: z
            .number()
            .int()
            .optional()
            .describe("Search radius in km"),
        min_price: z
            .number()
            .int()
            .optional()
            .describe("Minimum price in EUR"),
        max_price: z
            .number()
            .int()
            .optional()
            .describe("Maximum price in EUR"),
        page_count: z
            .number()
            .int()
            .min(1)
            .max(3)
            .optional()
            .describe("Pages to fetch (1-3, default 1). Lower max due to detail fetching."),
        max_concurrent_details: z
            .number()
            .int()
            .min(1)
            .max(10)
            .optional()
            .describe("Max concurrent detail fetches (1-10, default 5)"),
    }),
}, async (args) => {
    const params = {};
    if (args.query)
        params.query = args.query;
    if (args.location)
        params.location = args.location;
    if (args.radius !== undefined)
        params.radius = String(args.radius);
    if (args.min_price !== undefined)
        params.min_price = String(args.min_price);
    if (args.max_price !== undefined)
        params.max_price = String(args.max_price);
    if (args.page_count !== undefined)
        params.page_count = String(args.page_count);
    if (args.max_concurrent_details !== undefined)
        params.max_concurrent_details = String(args.max_concurrent_details);
    const data = await apiGet("/inserate-detailed", params);
    return textResult(data);
});
// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
async function main() {
    const transport = new StdioServerTransport();
    await server.connect(transport);
    console.error("Kleinanzeigen MCP server running on stdio");
}
main().catch((err) => {
    console.error("Fatal error:", err);
    process.exit(1);
});
//# sourceMappingURL=index.js.map