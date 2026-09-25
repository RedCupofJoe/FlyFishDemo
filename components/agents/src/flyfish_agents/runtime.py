"""HTTP runtime for every FlyFish agent."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from flyfish_common.artifacts import render_guide
from flyfish_common.http_client import UrllibClient
from flyfish_common.maas import MaasConfig
from flyfish_common.memory import MemoryHubClient, RecordingMemory
from flyfish_common.models import TripRequest, validate_trip
from flyfish_common.store import store_from_env
from flyfish_common.telemetry import configure_tracing, mark_http_status, server_span
from flyfish_agents.catalog import agent_card
from flyfish_agents.planner import RemoteSkills, plan_trip
from flyfish_agents.retrieve import OgxFileSearch, answer_question
from flyfish_agents.specialists import run_specialist
from flyfish_agents.tools import ToolCaller
from flyfish_indexer.__main__ import index_trip

SPECIALISTS = ("weather", "risk", "places", "consular")


def _public_url(agent: str) -> str:
    return os.environ.get("AGENT_PUBLIC_URL", f"http://{agent}-agent.flyfish-ai.svc:8080")


def _memory():
    url = os.environ.get("MEMORYHUB_URL", "").rstrip("/")
    api_key = os.environ.get("MEMORYHUB_API_KEY", "")
    if not url or not api_key:
        return RecordingMemory()

    class Transport:
        def __init__(self) -> None:
            self.http = UrllibClient()
            self.session = ""

        def request(self, payload: dict) -> dict:
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            if self.session:
                headers["Mcp-Session-Id"] = self.session
            response = self.http.post_json(f"{url}/mcp", payload, headers=headers)
            return response

    return MemoryHubClient(Transport(), api_key)


def _remote_from_env(http) -> RemoteSkills:
    urls = {}
    for skill in (*SPECIALISTS, "guide"):
        value = os.environ.get(f"{skill.upper()}_AGENT_URL", "").rstrip("/")
        if value:
            urls[skill] = value
    return RemoteSkills(http, urls)


def build_report(payload: dict, tools, memory, store) -> dict:
    request = TripRequest.from_dict(payload)
    http = getattr(tools, "http", UrllibClient())
    guide = plan_trip(
        request,
        tools,
        memory,
        store,
        remote=_remote_from_env(http),
        maas_config=MaasConfig.from_env(),
        maas_transport=http,
        fixture_mode=os.environ.get("FLYFISH_USE_FIXTURES") == "1",
    )
    rows: list[dict] = []
    index_trip(store, request.trip_id, rows.append, os.environ.get("AUTORAG_PATTERN_ID") or None)
    store.put_text(
        f"trips/{request.trip_id}/index.json",
        json.dumps(rows, indent=2),
        "application/json",
    )
    guide["chunks"] = len(rows)
    return guide


def handle_agent(agent: str, method: str, path: str, body: dict | None, tools, memory, store) -> tuple[int, dict]:
    if method == "GET" and path in ("/health", "/healthz"):
        return 200, {"status": "ok", "agent": agent}
    if method == "GET" and path == "/.well-known/agent-card.json":
        return 200, agent_card(agent, _public_url(agent))
    if method != "POST":
        return 404, {"error": "not found"}
    if agent in SPECIALISTS and path == "/v1/tasks":
        from flyfish_common.models import Country

        request = TripRequest.from_dict(body["trip"])
        country = Country(**body["country"])
        return 200, run_specialist(
            agent,
            request,
            country,
            tools,
            memory,
            store,
            MaasConfig.from_env(),
            getattr(tools, "http", None),
        )
    if agent == "guide" and path == "/v1/tasks":
        request = TripRequest.from_dict(body["trip"])
        markdown = render_guide(
            request,
            body["country_markdown"],
            fixture_mode=bool(body.get("fixture_mode")),
        )
        return 200, {"markdown": markdown}
    if agent == "planner" and path == "/v1/tasks":
        return 200, build_report(body["trip"], tools, memory, store)
    if agent == "response" and path == "/v1/chat":
        return _chat(body or {}, tools, memory, store)
    return 404, {"error": "not found"}


def _chat(body: dict, tools, memory, store) -> tuple[int, dict]:
    if body.get("trip"):
        errors = validate_trip(TripRequest.from_dict(body["trip"]))
        if errors:
            return 400, {"error": " ".join(errors)}
        planner_url = os.environ.get("PLANNER_AGENT_URL", "").rstrip("/")
        if planner_url:
            http = getattr(tools, "http", UrllibClient())
            report = http.post_json(f"{planner_url}/v1/tasks", {"trip": body["trip"]})
        else:
            report = build_report(body["trip"], tools, memory, store)
        return 200, {
            "role": "assistant",
            "trip_id": report["trip_id"],
            "content": report["markdown"],
            "grounded": True,
        }
    trip_id = body.get("trip_id", "")
    question = (body.get("message") or "").strip()
    if not trip_id or not question:
        return 400, {"error": "A follow-up needs trip_id and message."}
    http = getattr(tools, "http", UrllibClient())
    answer = answer_question(store, trip_id, question, OgxFileSearch.from_env(http))
    answer["role"] = "assistant"
    answer["trip_id"] = trip_id
    return 200, answer


def make_handler(agent: str):
    http = UrllibClient()
    tools = ToolCaller(http=http)
    memory = _memory()
    store = store_from_env(Path(os.environ.get("ARTIFACT_DIR", "/tmp/flyfish-artifacts")))

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            status, payload = _traced(agent, "GET", path, None, dict(self.headers), tools, memory, store)
            self._send(status, payload)

        def do_POST(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode() or "{}")
            except json.JSONDecodeError:
                self._send(400, {"error": "invalid JSON"})
                return
            status, payload = _traced(agent, "POST", path, body, dict(self.headers), tools, memory, store)
            self._send(status, payload)

        def do_OPTIONS(self):  # noqa: N802
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", "0")
            self.end_headers()

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

    return Handler


def _trip_id(body: dict | None) -> str:
    if not body:
        return ""
    trip = body.get("trip") if isinstance(body.get("trip"), dict) else {}
    return str(body.get("trip_id") or trip.get("trip_id") or "")


def _operation(path: str, body: dict | None) -> str:
    if path == "/v1/chat" and body and body.get("trip"):
        return "report"
    if path == "/v1/chat":
        return "follow_up"
    if path == "/v1/tasks":
        return "task"
    return path


def _traced(agent: str, method: str, path: str, body: dict | None, headers: dict, tools, memory, store):
    if method == "GET" and path in ("/health", "/healthz"):
        return handle_agent(agent, method, path, body, tools, memory, store)
    carrier = {str(key).lower(): value for key, value in headers.items()}
    attributes = {
        "flyfish.agent": agent,
        "flyfish.operation": _operation(path, body),
        "flyfish.trip_id": _trip_id(body),
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.agent.name": f"{agent}-agent",
        "http.request.method": method,
        "url.path": path,
    }
    with server_span(f"{method} {path}", carrier, attributes) as current:
        status, payload = handle_agent(agent, method, path, body, tools, memory, store)
        mark_http_status(current, status)
        return status, payload


def serve(agent: str) -> None:
    configure_tracing(f"{agent}-agent")
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), make_handler(agent))
    print(f"flyfish agent {agent} listening on {host}:{port}", flush=True)
    server.serve_forever()
