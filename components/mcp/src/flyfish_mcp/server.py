"""Stateless MCP streamable-HTTP server with a single tool."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from flyfish_common.http_client import UrllibClient
from flyfish_mcp.tools import TOOLS


def tool_result_payload(result) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(result.as_dict())}],
        "isError": False,
    }


def handle_rpc(tool_name: str, body: dict, http, clock=None) -> dict | None:
    method = body.get("method")
    request_id = body.get("id")
    spec = TOOLS[tool_name]
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        result = {
            "protocolVersion": "2025-03-26",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": f"flyfish-{tool_name}", "version": "0.1.0"},
        }
    elif method == "tools/list":
        result = {
            "tools": [
                {
                    "name": tool_name,
                    "description": spec["description"],
                    "inputSchema": spec["schema"],
                }
            ]
        }
    elif method == "tools/call":
        params = body.get("params") or {}
        name = params.get("name")
        if name != tool_name:
            return _error(request_id, -32602, f"This server only exposes {tool_name}")
        try:
            tool_result = spec["function"](params.get("arguments") or {}, http, clock=clock)
        except Exception as exc:  # noqa: BLE001 - surface tool bugs as MCP errors
            return _error(request_id, -32000, str(exc))
        result = tool_result_payload(tool_result)
    else:
        return _error(request_id, -32601, f"Unknown method {method}")
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def make_handler(tool_name: str, http=None, clock=None):
    client = http or UrllibClient()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):  # noqa: N802
            if self.path.split("?", 1)[0] in ("/health", "/healthz"):
                self._send(200, {"status": "ok", "tool": tool_name})
                return
            self._send(404, {"error": "not found"})

        def do_POST(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path not in ("/mcp", "/mcp/"):
                self._send(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode() or "{}")
            except json.JSONDecodeError:
                self._send(400, _error(None, -32700, "Parse error"))
                return
            response = handle_rpc(tool_name, body, client, clock=clock)
            if response is None:
                self._send(202, {})
                return
            self._send(200, response)

        def log_message(self, fmt: str, *args) -> None:
            return

        def _send(self, status: int, payload: dict) -> None:
            encoded = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(encoded)

        def do_OPTIONS(self):  # noqa: N802
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization")
            self.send_header("Content-Length", "0")
            self.end_headers()

    return Handler


def serve(tool_name: str, host: str = "0.0.0.0", port: int = 8080) -> None:
    if tool_name not in TOOLS:
        raise SystemExit(f"Unknown tool {tool_name}. Choose one of: {', '.join(sorted(TOOLS))}")
    server = ThreadingHTTPServer((host, port), make_handler(tool_name))
    print(f"flyfish MCP {tool_name} listening on {host}:{port}", flush=True)
    server.serve_forever()


def main() -> None:
    tool_name = os.environ.get("FLYFISH_TOOL", "")
    if not tool_name:
        raise SystemExit("Set FLYFISH_TOOL to one MCP tool name")
    serve(tool_name, port=int(os.environ.get("PORT", "8080")))
