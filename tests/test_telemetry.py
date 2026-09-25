import json
from pathlib import Path

import pytest

from flyfish_common.http_client import UrllibClient
from flyfish_common.telemetry import (
    MLflowSpanExporter,
    mlflow_otlp_headers,
    resolve_experiment_id,
    traces_endpoint,
)

otel = pytest.importorskip("opentelemetry.sdk.trace")
from opentelemetry import trace  # noqa: E402
from opentelemetry.propagate import inject  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter  # noqa: E402
from opentelemetry.trace import SpanKind  # noqa: E402


@pytest.fixture
def recording(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(trace, "_TRACER_PROVIDER", provider)
    monkeypatch.setattr(trace, "get_tracer_provider", lambda: provider)
    yield exporter
    provider.shutdown()


def test_traces_endpoint_adds_the_otlp_path_once():
    assert traces_endpoint("http://collector:4318") == "http://collector:4318/v1/traces"
    assert traces_endpoint("http://collector:4318/v1/traces/") == "http://collector:4318/v1/traces"


def test_mlflow_headers_carry_the_experiment_and_a_bearer_token():
    headers = mlflow_otlp_headers("tok", "17", "flyfish-ai")
    assert headers["x-mlflow-experiment-id"] == "17"
    assert headers["X-MLFLOW-WORKSPACE"] == "flyfish-ai"
    assert headers["Authorization"] == "Bearer tok"
    assert "Authorization" not in mlflow_otlp_headers("", "17", "flyfish-ai")


def test_experiment_id_is_created_or_reused():
    calls = []

    def opener(method, url, payload, headers):
        calls.append((method, url, payload))
        if method == "GET" and len(calls) == 1:
            return 404, {"error_code": "RESOURCE_DOES_NOT_EXIST"}
        if method == "POST":
            return 200, {"experiment_id": "17"}
        return 200, {"experiment": {"experiment_id": "17", "name": "flyfish-agents"}}

    assert resolve_experiment_id("https://mlflow.example:8443", "flyfish-agents", {}, opener) == "17"
    assert calls[1][0] == "POST"
    assert calls[1][2] == {"name": "flyfish-agents"}

    def raced(method, url, payload, headers):
        if method == "POST":
            return 400, {"error_code": "RESOURCE_ALREADY_EXISTS"}
        if method == "GET" and raced.n == 0:
            raced.n += 1
            return 404, {}
        return 200, {"experiment": {"experiment_id": "9"}}

    raced.n = 0
    assert resolve_experiment_id("https://mlflow.example:8443", "flyfish-agents", {}, raced) == "9"


def test_mlflow_exporter_rereads_the_service_account_token(tmp_path: Path):
    token = tmp_path / "token"
    token.write_text("alpha\n")
    seen = []

    class _Inner:
        def export(self, spans):
            return "ok"

        def shutdown(self):
            return None

    def factory(headers):
        seen.append(headers["Authorization"])
        return _Inner()

    exporter = MLflowSpanExporter(factory, str(token), "17", "flyfish-ai")
    assert exporter.export([]) == "ok"
    token.write_text("beta\n")
    assert exporter.export([]) == "ok"
    assert seen == ["Bearer alpha", "Bearer beta"]


def test_client_span_continues_the_agent_trace(recording, monkeypatch):
    captured = {}

    class _Response:
        status = 200

        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        captured["traceparent"] = request.get_header("Traceparent")
        return _Response()

    monkeypatch.setattr("flyfish_common.http_client.urlopen", fake_urlopen)
    tracer = trace.get_tracer("flyfish")
    with tracer.start_as_current_span("planner") as parent:
        UrllibClient().post_json("http://weather-agent.flyfish-ai.svc:8080/v1/tasks", {"ok": True})
        parent_id = parent.get_span_context().span_id
    client = next(span for span in recording.get_finished_spans() if span.kind == SpanKind.CLIENT)
    assert client.parent.span_id == parent_id
    assert client.attributes["server.address"] == "weather-agent.flyfish-ai.svc"
    assert client.attributes["url.path"] == "/v1/tasks"
    assert format(parent.get_span_context().trace_id, "032x") in captured["traceparent"]
    assert format(client.get_span_context().span_id, "016x") in captured["traceparent"]


def test_incoming_traceparent_is_the_parent_of_the_agent_span(recording, tmp_path, monkeypatch):
    from flyfish_common.memory import RecordingMemory
    from flyfish_common.store import FileArtifactStore
    from flyfish_agents.runtime import _traced
    from flyfish_agents.tools import ToolCaller
    from flyfish_mcp.fixtures import FixtureClient

    monkeypatch.setenv("FLYFISH_USE_FIXTURES", "1")
    tracer = trace.get_tracer("flyfish")
    with tracer.start_as_current_span("ui") as parent:
        carrier = {}
        inject(carrier)
        parent_id = parent.get_span_context().span_id
    status, payload = _traced(
        "response",
        "GET",
        "/.well-known/agent-card.json",
        None,
        carrier,
        ToolCaller(http=FixtureClient()),
        RecordingMemory(),
        FileArtifactStore(tmp_path),
    )
    assert status == 200
    assert payload["name"]
    server = next(span for span in recording.get_finished_spans() if span.kind == SpanKind.SERVER)
    assert server.parent.span_id == parent_id
    assert server.attributes["flyfish.agent"] == "response"
    assert "prompt" not in json.dumps(dict(server.attributes))


def test_health_checks_are_not_traced(recording, tmp_path):
    from flyfish_common.memory import RecordingMemory
    from flyfish_common.store import FileArtifactStore
    from flyfish_agents.runtime import _traced
    from flyfish_agents.tools import ToolCaller
    from flyfish_mcp.fixtures import FixtureClient

    status, payload = _traced(
        "response",
        "GET",
        "/health",
        None,
        {},
        ToolCaller(http=FixtureClient()),
        RecordingMemory(),
        FileArtifactStore(tmp_path),
    )
    assert status == 200
    assert payload["status"] == "ok"
    assert recording.get_finished_spans() == ()


def test_a_trip_records_one_span_per_skill(recording, tmp_path, monkeypatch):
    from flyfish_common.memory import RecordingMemory
    from flyfish_common.store import FileArtifactStore
    from flyfish_agents.planner import plan_trip
    from flyfish_agents.tools import ToolCaller
    from flyfish_mcp.fixtures import FixtureClient
    from tests.test_agents import _trip

    monkeypatch.setenv("FLYFISH_USE_FIXTURES", "1")
    plan_trip(_trip(), ToolCaller(http=FixtureClient()), RecordingMemory(), FileArtifactStore(tmp_path), fixture_mode=True)
    names = [span.name for span in recording.get_finished_spans()]
    assert names.count("flyfish.skill") == 8
    assert names.count("flyfish.guide") == 1
    skill = next(span for span in recording.get_finished_spans() if span.name == "flyfish.skill")
    assert skill.attributes["flyfish.trip_id"] == "trip-1"
    assert "citizenship" not in json.dumps(dict(skill.attributes))
