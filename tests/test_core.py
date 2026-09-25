import json
from datetime import date

import pytest

from flyfish_common.artifacts import render_country, render_guide, render_section
from flyfish_common.citations import validate_section
from flyfish_common.grounding import prose_is_grounded
from flyfish_common.maas import MaasConfig, grounded_summary
from flyfish_common.memory import MemoryKind, RecordingMemory, memory_record
from flyfish_common.models import Citation, CitationError, Country, Section, TripRequest, validate_trip
from flyfish_common.store import FileArtifactStore, S3ArtifactStore


def _citation():
    return Citation(title="Example", url="https://example.com/source", retrieved_at="2026-09-24")


def test_section_requires_a_citation():
    with pytest.raises(CitationError):
        validate_section(Section(heading="Weather", body="Warm", citations=[]))


def test_no_data_section_names_the_source():
    section = Section(
        heading="Crime statistics",
        body="",
        citations=[_citation()],
        no_data=True,
        no_data_reason="The World Bank indicator had no value.",
    )
    text = render_section(section)
    assert "had no value" in text
    assert "https://example.com/source" in text


def test_memory_kinds_use_memory_hub_scopes():
    personal = memory_record(MemoryKind.PERSONAL, "origin France", user_id="ada", trip_id="t1")
    episodic = memory_record(MemoryKind.EPISODIC, "visited the weather tool", user_id="ada", trip_id="t1")
    semantic = memory_record(MemoryKind.SEMANTIC, "France emergency number 112", user_id="ada", trip_id="t1", country_code="FR")
    assert personal.scope == "user"
    assert personal.metadata["kind"] == "personal"
    assert episodic.scope == "project"
    assert semantic.scope == "project"
    assert semantic.metadata["kind"] == "semantic"
    store = RecordingMemory()
    store.write(personal)
    store.write(semantic)
    found = store.search("emergency", MemoryKind.SEMANTIC)
    assert len(found) == 1
    assert store.search("origin", MemoryKind.EPISODIC) == []


def test_ungrounded_model_prose_is_rejected():
    result_summary = "Average high of 22.5 C."
    assert prose_is_grounded("The high was 22.5 C.", result_summary)
    assert not prose_is_grounded("The high was 40 C.", result_summary)


class _Maas:
    def post_json(self, url, payload, headers=None):
        return {"choices": [{"message": {"content": "The high was 99 C."}}]}


def test_reasoning_trace_is_dropped_before_grounding():
    from flyfish_common.models import ToolResult

    class _Think:
        def post_json(self, url, payload, headers=None):
            assert payload["model"] == "RedHatAI/gpt-oss-20b"
            assert payload["messages"][0]["content"].startswith("Reasoning: high")
            return {
                "choices": [
                    {
                        "message": {
                            "content": "<think>The high was 99 C.</think>The high was 22.5 C.",
                            "reasoning_content": "The high was 99 C.",
                        }
                    }
                ]
            }

    result = ToolResult(
        heading="Weather",
        summary="Average high of 22.5 C.",
        facts={"average_high_c": 22.5},
        citations=[_citation()],
    )
    prose = grounded_summary(
        result,
        MaasConfig("http://maas", "key", "RedHatAI/gpt-oss-20b"),
        _Think(),
    )
    assert prose == "The high was 22.5 C."


def test_default_reasoning_model_fits_one_l4():
    import os

    from flyfish_common.maas import REASONING_MODEL, MaasConfig

    assert REASONING_MODEL == "RedHatAI/gpt-oss-20b"
    previous = os.environ.get("MAAS_BASE_URL")
    os.environ["MAAS_BASE_URL"] = "http://guardrails.example"
    os.environ.pop("MAAS_MODEL", None)
    try:
        config = MaasConfig.from_env()
    finally:
        if previous is None:
            os.environ.pop("MAAS_BASE_URL", None)
        else:
            os.environ["MAAS_BASE_URL"] = previous
    assert config is not None
    assert config.model == REASONING_MODEL


def test_maas_falls_back_when_the_model_adds_numbers():
    from flyfish_common.models import ToolResult

    result = ToolResult(
        heading="Weather",
        summary="Average high of 22.5 C.",
        facts={"average_high_c": 22.5},
        citations=[_citation()],
    )
    prose = grounded_summary(result, MaasConfig("http://maas", "key", "granite"), _Maas())
    assert prose == "Average high of 22.5 C."


def test_trip_validation_and_guide_order():
    request = TripRequest(
        trip_id="t1",
        countries=(Country("FR", "France"), Country("JP", "Japan")),
        start_date="2026-06-01",
        end_date="2026-06-14",
        season="summer",
        origin=Country("US", "United States"),
        citizenship_status="citizen",
        prompt="Focus on trains.",
    )
    assert validate_trip(request, today=date(2026, 1, 1)) == []
    france = render_country(
        request.countries[0],
        [Section(heading="Weather", body="Mild.", citations=[_citation()])],
    )
    japan = render_country(
        request.countries[1],
        [Section(heading="Weather", body="Humid.", citations=[_citation()])],
    )
    guide = render_guide(request, [france, japan])
    assert guide.index("France") < guide.index("Japan")
    assert "not legal advice" in guide.lower()
    assert "Focus on trains." in guide


def test_file_and_s3_stores(tmp_path):
    store = FileArtifactStore(tmp_path)
    store.put_text("trips/t1/guide.md", "hello")
    assert store.get_text("trips/t1/guide.md") == "hello"
    assert store.list_keys("trips/t1/") == ["trips/t1/guide.md"]
    with pytest.raises(ValueError):
        store.put_text("../etc/passwd", "no")

    class Client:
        def __init__(self):
            self.objects = {}

        def put_object(self, Bucket, Key, Body, ContentType):
            self.objects[Key] = Body.decode()

        def get_object(self, Bucket, Key):
            class Body:
                def __init__(self, text):
                    self._text = text

                def read(self):
                    return self._text.encode()

            return {"Body": Body(self.objects[Key])}

        def list_objects_v2(self, Bucket, Prefix):
            return {"Contents": [{"Key": key} for key in self.objects if key.startswith(Prefix)]}

    s3 = S3ArtifactStore("bucket", Client())
    s3.put_text("trips/t1/FR.md", "france")
    assert s3.get_text("trips/t1/FR.md") == "france"
    assert s3.list_keys("trips/t1/") == ["trips/t1/FR.md"]


def test_memory_hub_client_sends_kind_metadata():
    calls = []

    class Transport:
        def request(self, payload):
            calls.append(payload)
            name = payload["params"]["name"]
            if name == "register_session":
                return {"result": {"content": [{"type": "text", "text": "ok"}]}}
            return {"result": {"content": [{"type": "text", "text": json.dumps({"id": "m1"})}]}}

    from flyfish_common.memory import MemoryHubClient

    client = MemoryHubClient(Transport(), "mh-dev-test")
    record = memory_record(MemoryKind.EPISODIC, "guide written", user_id="ada", trip_id="t1")
    assert client.write(record) == {"id": "m1"}
    write_call = calls[1]["params"]
    assert write_call["name"] == "write_memory"
    assert write_call["arguments"]["scope"] == "project"
    assert write_call["arguments"]["metadata"]["kind"] == "episodic"
    assert calls[0]["params"]["name"] == "register_session"
