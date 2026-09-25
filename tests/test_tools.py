import json
from datetime import date

import pytest

from flyfish_common.http_client import HttpError
from flyfish_mcp.fixtures import FixtureClient
from flyfish_mcp.server import handle_rpc
from flyfish_mcp.tools import TOOLS, crime_statistics, travel_advisory, weather


class Boom:
    def get_json(self, url, headers=None, params=None):
        raise HttpError(f"down {url}")


def test_weather_uses_archive_and_cites_it():
    result = weather(
        {
            "country_name": "France",
            "country_code": "FR",
            "start_date": "2026-06-01",
            "end_date": "2026-06-03",
            "season": "summer",
        },
        FixtureClient(),
        clock=lambda: "2026-09-24",
    )
    assert result.no_data is False
    assert "22.5" in result.summary or "23.2" in result.summary
    assert "not a forecast" in result.summary
    assert result.facts["reference_start"] == "2025-06-01"
    assert any("open-meteo.com" in citation.url for citation in result.citations)


def test_weather_reports_a_gap_when_the_source_fails():
    result = weather(
        {
            "country_name": "France",
            "country_code": "FR",
            "start_date": "2026-06-01",
            "end_date": "2026-06-03",
            "season": "summer",
        },
        Boom(),
        clock=lambda: "2026-09-24",
    )
    assert result.no_data is True
    assert result.citations[0].url.startswith("https://")


def test_advisory_and_crime_parsers():
    advisory = travel_advisory({"country_name": "France", "country_code": "FR"}, FixtureClient(), clock=lambda: "2026-09-24")
    assert "Level 2" in advisory.summary
    crime = crime_statistics({"country_name": "France", "country_code": "FR"}, FixtureClient(), clock=lambda: "2026-09-24")
    assert crime.facts["value_per_100000"] == 1.1
    assert crime.facts["year"] == "2021"
    assert "100,000" in crime.summary


def test_crime_gap_when_value_is_null():
    class Client:
        def get_json(self, url, headers=None, params=None):
            return [{}, [{"value": None, "date": "2021"}]]

    result = crime_statistics({"country_name": "France", "country_code": "FR"}, Client(), clock=lambda: "2026-09-24")
    assert result.no_data is True
    assert "no homicide-rate value" in result.no_data_reason


def test_each_tool_returns_a_citation_from_fixtures():
    client = FixtureClient()
    clock = lambda: "2026-09-24"  # noqa: E731
    common = {"country_name": "France", "country_code": "FR"}
    for name, spec in TOOLS.items():
        arguments = dict(common)
        if name == "weather":
            arguments.update({"start_date": "2026-06-01", "end_date": "2026-06-08", "season": "summer"})
        if name == "embassy":
            arguments.update({"origin_country_name": "United States", "origin_country_code": "US"})
        result = spec["function"](arguments, client, clock=clock)
        assert result.citations, name
        assert result.citations[0].url.startswith("https://"), name
        if result.no_data:
            assert result.no_data_reason
        else:
            assert result.summary


def test_mcp_protocol_lists_and_calls_one_tool():
    listed = handle_rpc("landmarks", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, FixtureClient())
    assert listed["result"]["tools"][0]["name"] == "landmarks"
    called = handle_rpc(
        "landmarks",
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "landmarks", "arguments": {"country_name": "France", "country_code": "FR"}},
        },
        FixtureClient(),
        clock=lambda: "2026-09-24",
    )
    payload = json.loads(called["result"]["content"][0]["text"])
    assert "heritage site" in payload["summary"]
    rejected = handle_rpc(
        "landmarks",
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "weather", "arguments": {}}},
        FixtureClient(),
    )
    assert rejected["error"]["code"] == -32602


def test_leap_day_reference_year_does_not_crash():
    result = weather(
        {
            "country_name": "France",
            "country_code": "FR",
            "start_date": "2028-02-29",
            "end_date": "2028-03-02",
            "season": "winter",
        },
        FixtureClient(),
        clock=lambda: "2026-09-24",
    )
    assert result.facts["reference_start"] == "2027-02-28"
    assert date.fromisoformat(result.facts["reference_end"])
