import json
from http.server import ThreadingHTTPServer
from threading import Thread

from flyfish_common.memory import MemoryKind, RecordingMemory
from flyfish_common.models import Country, TripRequest
from flyfish_common.store import FileArtifactStore
from flyfish_agents.planner import RemoteSkills, plan_trip
from flyfish_agents.retrieve import answer_from_guide
from flyfish_agents.runtime import handle_agent, make_handler
from flyfish_agents.tools import ToolCaller
from flyfish_indexer.chunk import chunk_markdown, index_rows
from flyfish_indexer.ogx import vector_store_file_body
from flyfish_mcp.fixtures import FixtureClient


def _trip():
    return TripRequest(
        trip_id="trip-1",
        countries=(Country("FR", "France"), Country("JP", "Japan")),
        start_date="2026-06-01",
        end_date="2026-06-08",
        season="summer",
        origin=Country("US", "United States"),
        citizenship_status="citizen",
        prompt="I want trains, museums, and emergency numbers.",
        user_id="ada",
    )


def test_planner_writes_three_memory_kinds_and_a_guide(tmp_path):
    memory = RecordingMemory()
    store = FileArtifactStore(tmp_path)
    tools = ToolCaller(http=FixtureClient(), urls={})
    result = plan_trip(_trip(), tools, memory, store, fixture_mode=True)
    kinds = {record.kind for record in memory.records}
    assert kinds == {MemoryKind.PERSONAL, MemoryKind.EPISODIC, MemoryKind.SEMANTIC}
    assert any(record.scope == "user" for record in memory.records)
    guide = result["markdown"]
    assert guide.index("France") < guide.index("Japan")
    assert "fixture" in guide.lower()
    assert "not legal advice" in guide.lower()
    assert store.get_text("trips/trip-1/guide.md") == guide
    assert "trips/trip-1/FR-weather.md" in store.list_keys("trips/trip-1/")
    rows = index_rows("trip-1", "trips/trip-1/guide.md", guide, "pattern-a")
    assert rows
    assert rows[0]["autorag_pattern"] == "pattern-a"
    assert chunk_markdown(guide)


def test_follow_up_quotes_the_report_and_refuses_unknowns(tmp_path):
    memory = RecordingMemory()
    store = FileArtifactStore(tmp_path)
    plan_trip(_trip(), ToolCaller(http=FixtureClient(), urls={}), memory, store)
    guide = store.get_text("trips/trip-1/guide.md")
    weather = answer_from_guide(guide, "What was the weather in France?")
    assert weather["grounded"] is True
    assert "Weather" in weather["content"]
    missing = answer_from_guide(guide, "What is the parking price at the secret garage?")
    assert "does not contain" in missing["content"]


def test_response_agent_chat_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACT_DIR", str(tmp_path))
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.delenv("PLANNER_AGENT_URL", raising=False)
    monkeypatch.delenv("MEMORYHUB_URL", raising=False)
    tools = ToolCaller(http=FixtureClient(), urls={})
    memory = RecordingMemory()
    store = FileArtifactStore(tmp_path)
    status, report = handle_agent(
        "response",
        "POST",
        "/v1/chat",
        {"trip": _trip().as_dict()},
        tools,
        memory,
        store,
    )
    assert status == 200
    assert "France" in report["content"]
    status, answer = handle_agent(
        "response",
        "POST",
        "/v1/chat",
        {"trip_id": report["trip_id"], "message": "Which emergency numbers are listed?"},
        tools,
        memory,
        store,
    )
    assert status == 200
    assert "112" in answer["content"]
    card_status, card = handle_agent("response", "GET", "/.well-known/agent-card.json", None, tools, memory, store)
    assert card_status == 200
    assert card["name"] == "flyfish-response"


def test_remote_skills_delegate_to_specialist_and_guide(tmp_path):
    store = FileArtifactStore(tmp_path)
    memory = RecordingMemory()
    tools = ToolCaller(http=FixtureClient(), urls={})

    class FakeHttp:
        def post_json(self, url, payload, headers=None):
            if url.endswith("/weather-agent/v1/tasks"):
                body = handle_agent("weather", "POST", "/v1/tasks", payload, tools, memory, store)[1]
                return body
            if url.endswith("/guide-agent/v1/tasks"):
                return handle_agent("guide", "POST", "/v1/tasks", payload, tools, memory, store)[1]
            raise AssertionError(url)

    remote = RemoteSkills(FakeHttp(), {"weather": "http://weather-agent", "guide": "http://guide-agent"})
    request = TripRequest(
        trip_id="trip-2",
        countries=(Country("FR", "France"),),
        start_date="2026-06-01",
        end_date="2026-06-08",
        season="summer",
        origin=Country("US", "United States"),
        citizenship_status="visa_holder",
        prompt="Museums.",
    )
    result = plan_trip(request, tools, memory, store, remote=remote)
    assert "France" in result["markdown"]
    assert "Weather" in result["markdown"]
    assert vector_store_file_body("file-123") == {"file_id": "file-123"}


def test_fixture_mode_overrides_the_live_client(monkeypatch):
    monkeypatch.setenv("FLYFISH_USE_FIXTURES", "1")

    class Live:
        def get_json(self, url, headers=None, params=None):
            raise AssertionError(url)

    result = ToolCaller(http=Live(), urls={}).call(
        "emergency",
        {"country_name": "France", "country_code": "FR"},
    )
    assert result.facts["emergency_numbers"] == ["112"]


def test_agent_http_server_serves_a_card():
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler("planner"))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        from urllib.request import urlopen

        with urlopen(f"http://127.0.0.1:{server.server_address[1]}/.well-known/agent-card.json") as response:
            card = json.loads(response.read().decode())
        assert card["name"] == "flyfish-planner"
    finally:
        server.shutdown()
