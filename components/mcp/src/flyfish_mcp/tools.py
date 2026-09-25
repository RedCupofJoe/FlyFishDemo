"""Public-data tools. Each function returns a ToolResult and does not invent figures."""

from __future__ import annotations

import os
from datetime import date, timedelta
from urllib.parse import quote

from flyfish_common.http_client import HttpError
from flyfish_common.models import Citation, ToolResult

OPEN_METEO_GEO = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
ADVISORY_URL = "https://cadataapi.state.gov/api/TravelAdvisories"
WORLDBANK_INDICATOR = "VC.IHR.PSRC.P5"
WORLDBANK_PAGE = "https://data.worldbank.org/indicator/VC.IHR.PSRC.P5"
WIKIDATA = "https://query.wikidata.org/sparql"
WIKIDATA_PAGE = "https://query.wikidata.org/"


def _previous_year(value: date) -> date:
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return value.replace(year=value.year - 1, day=28)


def _today(clock) -> str:
    if clock is not None:
        return clock()
    return date.today().isoformat()


def _cite(title: str, url: str, retrieved_at: str) -> Citation:
    return Citation(title=title, url=url, retrieved_at=retrieved_at)


def _gap(heading: str, reason: str, citation: Citation) -> ToolResult:
    return ToolResult(
        heading=heading,
        summary="",
        facts={},
        citations=[citation],
        no_data=True,
        no_data_reason=reason,
    )


def weather(arguments: dict, http, clock=None) -> ToolResult:
    heading = "Weather"
    country = arguments["country_name"]
    retrieved = _today(clock)
    geo_url = OPEN_METEO_GEO
    try:
        geo = http.get_json(
            geo_url,
            params={"name": country, "count": "1", "language": "en", "format": "json"},
        )
    except HttpError as exc:
        return _gap(heading, f"Open-Meteo geocoding had no data: {exc}", _cite("Open-Meteo geocoding", geo_url, retrieved))
    results = geo.get("results") or []
    if not results:
        return _gap(
            heading,
            f"Open-Meteo geocoding returned no location for {country}.",
            _cite("Open-Meteo geocoding", geo_url, retrieved),
        )
    place = results[0]
    lat = place["latitude"]
    lon = place["longitude"]
    start = date.fromisoformat(arguments["start_date"])
    end = date.fromisoformat(arguments["end_date"])
    # The archive API is a seasonal reference for the same dates one year earlier.
    # It is not a forecast, and the summary says so.
    ref_start = _previous_year(start)
    ref_end = _previous_year(end)
    if ref_end - ref_start > timedelta(days=31):
        ref_end = ref_start + timedelta(days=31)
    archive_url = OPEN_METEO_ARCHIVE
    try:
        archive = http.get_json(
            archive_url,
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": ref_start.isoformat(),
                "end_date": ref_end.isoformat(),
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto",
            },
        )
    except HttpError as exc:
        return _gap(heading, f"Open-Meteo archive had no data: {exc}", _cite("Open-Meteo archive", archive_url, retrieved))
    daily = archive.get("daily") or {}
    highs = [value for value in daily.get("temperature_2m_max") or [] if value is not None]
    lows = [value for value in daily.get("temperature_2m_min") or [] if value is not None]
    rain = [value for value in daily.get("precipitation_sum") or [] if value is not None]
    if not highs or not lows:
        return _gap(
            heading,
            f"Open-Meteo archive returned no temperatures for {country}.",
            _cite("Open-Meteo archive", archive_url, retrieved),
        )
    high = round(sum(highs) / len(highs), 1)
    low = round(sum(lows) / len(lows), 1)
    wet = round(sum(rain), 1) if rain else 0.0
    place_name = place.get("name", country)
    summary = (
        f"For {place_name}, the Open-Meteo archive for {ref_start.isoformat()} to {ref_end.isoformat()} "
        f"(the same dates one year before this trip, used as seasonal context for {arguments.get('season', 'the selected time of year')}) "
        f"shows an average daily high of {high} C, an average daily low of {low} C, "
        f"and {wet} mm of precipitation over {len(highs)} days. This is archived weather, not a forecast."
    )
    return ToolResult(
        heading=heading,
        summary=summary,
        facts={
            "place": place_name,
            "latitude": lat,
            "longitude": lon,
            "reference_start": ref_start.isoformat(),
            "reference_end": ref_end.isoformat(),
            "average_high_c": high,
            "average_low_c": low,
            "precipitation_mm": wet,
            "days": len(highs),
        },
        citations=[
            _cite("Open-Meteo geocoding", geo_url, retrieved),
            _cite("Open-Meteo archive", archive_url, retrieved),
        ],
    )


def _advisory_rows(payload) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "advisories", "TravelAdvisories"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def _row_text(row: dict, *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def travel_advisory(arguments: dict, http, clock=None) -> ToolResult:
    heading = "Travel advisory"
    retrieved = _today(clock)
    url = os.environ.get("TRAVEL_ADVISORY_URL", ADVISORY_URL)
    country = arguments["country_name"].lower()
    code = arguments["country_code"].lower()
    try:
        payload = http.get_json(url)
    except HttpError as exc:
        return _gap(heading, f"The travel advisory source had no data: {exc}", _cite("Travel advisories", url, retrieved))
    match = None
    for row in _advisory_rows(payload):
        row_code = _row_text(row, "country_code", "iso2", "ISO", "iso_code").lower()
        row_name = _row_text(row, "country", "Country", "title", "Title", "name").lower()
        if row_code == code or country in row_name or row_name in country:
            match = row
            break
    if match is None:
        return _gap(
            heading,
            f"The travel advisory source had no matching entry for {arguments['country_name']}.",
            _cite("Travel advisories", url, retrieved),
        )
    level = _row_text(match, "level", "advisory_level", "AdvisoryLevel", "advisoryLevel")
    summary_text = _row_text(match, "summary", "Summary", "advisory_text", "text")
    updated = _row_text(match, "updated", "date_updated", "DateUpdated", "published")
    link = _row_text(match, "url", "link", "Link") or url
    if not level and not summary_text:
        return _gap(
            heading,
            f"The travel advisory source listed {arguments['country_name']} without a level or summary.",
            _cite("Travel advisories", link, retrieved),
        )
    parts = [f"Travel advisory for {arguments['country_name']}."]
    if level:
        parts.append(f"Level: {level}.")
    if updated:
        parts.append(f"Source update date: {updated}.")
    if summary_text:
        parts.append(summary_text)
    return ToolResult(
        heading=heading,
        summary=" ".join(parts),
        facts={"level": level, "summary": summary_text, "updated": updated, "url": link},
        citations=[_cite("Travel advisories", link, retrieved)],
    )


def crime_statistics(arguments: dict, http, clock=None) -> ToolResult:
    heading = "Crime statistics"
    retrieved = _today(clock)
    code = arguments["country_code"].lower()
    url = f"https://api.worldbank.org/v2/country/{code}/indicator/{WORLDBANK_INDICATOR}"
    try:
        payload = http.get_json(url, params={"format": "json", "mrv": "1"})
    except HttpError as exc:
        return _gap(
            heading,
            f"The World Bank homicide indicator had no data: {exc}",
            _cite("World Bank intentional homicides per 100,000 people", WORLDBANK_PAGE, retrieved),
        )
    rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else None
    row = rows[0] if isinstance(rows, list) and rows else None
    value = row.get("value") if isinstance(row, dict) else None
    if not isinstance(row, dict) or value is None:
        return _gap(
            heading,
            f"The World Bank indicator {WORLDBANK_INDICATOR} had no homicide-rate value for {arguments['country_name']}.",
            _cite("World Bank intentional homicides per 100,000 people", WORLDBANK_PAGE, retrieved),
        )
    year = row.get("date", "")
    summary = (
        f"World Bank indicator {WORLDBANK_INDICATOR} reports {value} intentional homicides "
        f"per 100,000 people for {arguments['country_name']} in {year}. "
        "This is a national homicide rate, not a city-level or tourist-crime rate."
    )
    return ToolResult(
        heading=heading,
        summary=summary,
        facts={"indicator": WORLDBANK_INDICATOR, "value_per_100000": value, "year": year},
        citations=[_cite("World Bank intentional homicides per 100,000 people", WORLDBANK_PAGE, retrieved)],
    )


def _sparql(http, query: str):
    return http.get_json(
        WIKIDATA,
        params={"query": query, "format": "json"},
        headers={"Accept": "application/sparql-results+json", "User-Agent": "FlyFishDemo/0.1"},
    )


def _bindings(payload) -> list[dict]:
    return ((payload or {}).get("results") or {}).get("bindings") or []


def _label(binding: dict, key: str) -> str:
    value = binding.get(key) or {}
    return value.get("value", "")


def _places(arguments: dict, http, clock, heading: str, where: str, empty: str) -> ToolResult:
    retrieved = _today(clock)
    code = arguments["country_code"].upper()
    query = f"""
SELECT ?itemLabel ?article WHERE {{
  ?item wdt:P17 ?country .
  ?country wdt:P297 "{code}" .
  {where}
  OPTIONAL {{
    ?article schema:about ?item .
    ?article schema:isPartOf <https://en.wikipedia.org/> .
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT 8
""".strip()
    try:
        payload = _sparql(http, query)
    except HttpError as exc:
        return _gap(heading, f"Wikidata had no data: {exc}", _cite("Wikidata query service", WIKIDATA_PAGE, retrieved))
    names = []
    links = []
    for binding in _bindings(payload):
        label = _label(binding, "itemLabel")
        if not label or label.startswith("Q"):
            continue
        names.append(label)
        article = _label(binding, "article")
        if article:
            links.append(article)
    if not names:
        return _gap(heading, empty, _cite("Wikidata query service", WIKIDATA_PAGE, retrieved))
    unique = list(dict.fromkeys(names))
    summary = f"Wikidata lists these places in {arguments['country_name']}: {', '.join(unique)}."
    citations = [_cite("Wikidata query service", WIKIDATA_PAGE, retrieved)]
    citations.extend(_cite(link.rsplit("/", 1)[-1].replace("_", " "), link, retrieved) for link in links[:3])
    return ToolResult(
        heading=heading,
        summary=summary,
        facts={"places": unique},
        citations=citations,
    )


def landmarks(arguments: dict, http, clock=None) -> ToolResult:
    return _places(
        arguments,
        http,
        clock,
        "Landmarks",
        "?item wdt:P1435 wd:Q9259 .",
        f"Wikidata returned no UNESCO World Heritage Sites for {arguments['country_name']}.",
    )


def attractions(arguments: dict, http, clock=None) -> ToolResult:
    return _places(
        arguments,
        http,
        clock,
        "Tourist attractions",
        "?item wdt:P31/wdt:P279* wd:Q570116 .",
        f"Wikidata returned no tourist attractions for {arguments['country_name']}.",
    )


def nightlife(arguments: dict, http, clock=None) -> ToolResult:
    return _places(
        arguments,
        http,
        clock,
        "Nightlife",
        "VALUES ?kind { wd:Q622425 wd:Q53060 } ?item wdt:P31 ?kind .",
        f"Wikidata returned no nightclubs or bars for {arguments['country_name']}.",
    )


def trends(arguments: dict, http, clock=None) -> ToolResult:
    heading = "Emerging travel context"
    retrieved = _today(clock)
    title = "Tourism_in_" + arguments["country_name"].replace(" ", "_")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
    page = f"https://en.wikipedia.org/wiki/{quote(title)}"
    try:
        payload = http.get_json(url)
    except HttpError as exc:
        return _gap(
            heading,
            f"The English Wikipedia tourism summary had no data: {exc}",
            _cite("English Wikipedia", page, retrieved),
        )
    extract = (payload.get("extract") or "").strip()
    if payload.get("type") == "disambiguation" or not extract:
        return _gap(
            heading,
            f"English Wikipedia had no tourism summary for {arguments['country_name']}.",
            _cite("English Wikipedia", page, retrieved),
        )
    summary = (
        "The following text is the English Wikipedia summary of the country's tourism page. "
        "It is published background, not a measured forecast of emerging trends. "
        + extract
    )
    return ToolResult(
        heading=heading,
        summary=summary,
        facts={"title": payload.get("title", title), "extract": extract},
        citations=[_cite(payload.get("title") or "English Wikipedia", payload.get("content_urls", {}).get("desktop", {}).get("page") or page, retrieved)],
    )


def emergency(arguments: dict, http, clock=None) -> ToolResult:
    heading = "Emergency services"
    retrieved = _today(clock)
    code = arguments["country_code"].upper()
    query = f"""
SELECT ?phone WHERE {{
  ?country wdt:P297 "{code}" .
  ?country wdt:P2852 ?phone .
}}
""".strip()
    try:
        payload = _sparql(http, query)
    except HttpError as exc:
        return _gap(heading, f"Wikidata had no data: {exc}", _cite("Wikidata query service", WIKIDATA_PAGE, retrieved))
    numbers = []
    for binding in _bindings(payload):
        phone = _label(binding, "phone")
        if phone:
            numbers.append(phone)
    unique = list(dict.fromkeys(numbers))
    if not unique:
        return _gap(
            heading,
            f"Wikidata property P2852 had no emergency telephone number for {arguments['country_name']}.",
            _cite("Wikidata query service", WIKIDATA_PAGE, retrieved),
        )
    summary = (
        f"Wikidata lists these emergency telephone numbers for {arguments['country_name']}: "
        f"{', '.join(unique)}. Confirm the number with a local official source before relying on it."
    )
    return ToolResult(
        heading=heading,
        summary=summary,
        facts={"emergency_numbers": unique},
        citations=[_cite("Wikidata emergency telephone number (P2852)", WIKIDATA_PAGE, retrieved)],
    )


def embassy(arguments: dict, http, clock=None) -> ToolResult:
    heading = "Embassies"
    retrieved = _today(clock)
    host = arguments["country_code"].upper()
    origin = arguments["origin_country_code"].upper()
    query = f"""
SELECT ?missionLabel ?website WHERE {{
  ?mission wdt:P31/wdt:P279* wd:Q3917681 .
  ?mission wdt:P17 ?host .
  ?host wdt:P297 "{host}" .
  ?mission wdt:P137 ?represented .
  ?represented wdt:P297 "{origin}" .
  OPTIONAL {{ ?mission wdt:P856 ?website }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT 5
""".strip()
    try:
        payload = _sparql(http, query)
    except HttpError as exc:
        return _gap(heading, f"Wikidata had no data: {exc}", _cite("Wikidata query service", WIKIDATA_PAGE, retrieved))
    missions = []
    for binding in _bindings(payload):
        label = _label(binding, "missionLabel")
        if not label or label.startswith("Q"):
            continue
        website = _label(binding, "website")
        missions.append({"name": label, "website": website})
    if not missions:
        return _gap(
            heading,
            (
                f"Wikidata returned no embassy of {arguments['origin_country_name']} "
                f"in {arguments['country_name']}."
            ),
            _cite("Wikidata query service", WIKIDATA_PAGE, retrieved),
        )
    rendered = []
    for mission in missions:
        if mission["website"]:
            rendered.append(f"{mission['name']} ({mission['website']})")
        else:
            rendered.append(mission["name"])
    summary = (
        f"Wikidata lists these diplomatic missions of {arguments['origin_country_name']} "
        f"in {arguments['country_name']}: {'; '.join(rendered)}. "
        "Confirm hours and services with the mission before a visit."
    )
    return ToolResult(
        heading=heading,
        summary=summary,
        facts={"missions": missions},
        citations=[_cite("Wikidata query service", WIKIDATA_PAGE, retrieved)],
    )


TOOLS = {
    "weather": {
        "description": "Seasonal weather context from the Open-Meteo archive for the same dates one year earlier.",
        "function": weather,
        "schema": {
            "type": "object",
            "properties": {
                "country_name": {"type": "string"},
                "country_code": {"type": "string"},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "season": {"type": "string"},
            },
            "required": ["country_name", "country_code", "start_date", "end_date", "season"],
        },
    },
    "travel_advisory": {
        "description": "Travel advisory level and summary for one country.",
        "function": travel_advisory,
        "schema": {
            "type": "object",
            "properties": {
                "country_name": {"type": "string"},
                "country_code": {"type": "string"},
            },
            "required": ["country_name", "country_code"],
        },
    },
    "crime_statistics": {
        "description": "National intentional-homicide rate from the World Bank.",
        "function": crime_statistics,
        "schema": {
            "type": "object",
            "properties": {
                "country_name": {"type": "string"},
                "country_code": {"type": "string"},
            },
            "required": ["country_name", "country_code"],
        },
    },
    "landmarks": {
        "description": "UNESCO World Heritage Sites in a country from Wikidata.",
        "function": landmarks,
        "schema": {
            "type": "object",
            "properties": {
                "country_name": {"type": "string"},
                "country_code": {"type": "string"},
            },
            "required": ["country_name", "country_code"],
        },
    },
    "attractions": {
        "description": "Tourist attractions in a country from Wikidata.",
        "function": attractions,
        "schema": {
            "type": "object",
            "properties": {
                "country_name": {"type": "string"},
                "country_code": {"type": "string"},
            },
            "required": ["country_name", "country_code"],
        },
    },
    "nightlife": {
        "description": "Nightclubs and bars in a country from Wikidata.",
        "function": nightlife,
        "schema": {
            "type": "object",
            "properties": {
                "country_name": {"type": "string"},
                "country_code": {"type": "string"},
            },
            "required": ["country_name", "country_code"],
        },
    },
    "trends": {
        "description": "English Wikipedia tourism summary, labeled as background rather than a forecast.",
        "function": trends,
        "schema": {
            "type": "object",
            "properties": {
                "country_name": {"type": "string"},
                "country_code": {"type": "string"},
            },
            "required": ["country_name", "country_code"],
        },
    },
    "emergency": {
        "description": "Emergency telephone numbers from Wikidata.",
        "function": emergency,
        "schema": {
            "type": "object",
            "properties": {
                "country_name": {"type": "string"},
                "country_code": {"type": "string"},
            },
            "required": ["country_name", "country_code"],
        },
    },
    "embassy": {
        "description": "Diplomatic missions of the traveler's origin country in the destination.",
        "function": embassy,
        "schema": {
            "type": "object",
            "properties": {
                "country_name": {"type": "string"},
                "country_code": {"type": "string"},
                "origin_country_name": {"type": "string"},
                "origin_country_code": {"type": "string"},
            },
            "required": ["country_name", "country_code", "origin_country_name", "origin_country_code"],
        },
    },
}
