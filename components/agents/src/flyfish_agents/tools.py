"""Call one MCP server per tool, or the in-process function when no URL is set."""

from __future__ import annotations

import json
import os

from flyfish_common.http_client import UrllibClient
from flyfish_common.models import Citation, ToolResult
from flyfish_mcp.fixtures import FixtureClient
from flyfish_mcp.tools import TOOLS

_ENV = {
    "weather": "WEATHER_MCP_URL",
    "travel_advisory": "TRAVEL_ADVISORY_MCP_URL",
    "crime_statistics": "CRIME_STATS_MCP_URL",
    "landmarks": "LANDMARKS_MCP_URL",
    "attractions": "ATTRACTIONS_MCP_URL",
    "nightlife": "NIGHTLIFE_MCP_URL",
    "trends": "TRENDS_MCP_URL",
    "emergency": "EMERGENCY_MCP_URL",
    "embassy": "EMBASSY_MCP_URL",
}


class ToolCaller:
    def __init__(self, http=None, urls: dict | None = None, clock=None) -> None:
        if os.environ.get("FLYFISH_USE_FIXTURES") == "1":
            http = FixtureClient()
        self.http = http or UrllibClient()
        self.urls = urls if urls is not None else {name: os.environ.get(env, "").rstrip("/") for name, env in _ENV.items()}
        self.clock = clock

    def call(self, name: str, arguments: dict) -> ToolResult:
        base = self.urls.get(name, "")
        if not base:
            return TOOLS[name]["function"](arguments, self.http, clock=self.clock)
        response = self.http.post_json(
            f"{base}/mcp",
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
        )
        content = response["result"]["content"][0]["text"]
        payload = json.loads(content)
        return ToolResult(
            heading=payload["heading"],
            summary=payload["summary"],
            facts=payload["facts"],
            citations=[Citation(**item) for item in payload["citations"]],
            no_data=payload["no_data"],
            no_data_reason=payload["no_data_reason"],
        )
