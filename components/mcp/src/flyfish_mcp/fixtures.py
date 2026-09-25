"""Offline HTTP responses for local demonstration and tests.

Fixture mode is labeled in the guide. The figures below are sample payloads
for the parsers, not live travel data.
"""

from __future__ import annotations

import re

from flyfish_common.http_client import HttpError

_ADVISORIES = {
    "FR": ("France", "Level 2: Exercise Increased Caution", "Exercise increased caution in France."),
    "JP": ("Japan", "Level 1: Exercise Normal Precautions", "Exercise normal precautions in Japan."),
    "US": ("United States", "Level 1: Exercise Normal Precautions", "Exercise normal precautions in the United States."),
}


class FixtureClient:
    def get_json(self, url: str, headers: dict | None = None, params: dict | None = None):
        params = params or {}
        if "geocoding-api.open-meteo.com" in url:
            return {"results": [{"name": params.get("name", "Sample"), "latitude": 48.85, "longitude": 2.35, "country_code": "FR"}]}
        if "archive-api.open-meteo.com" in url:
            return {
                "daily": {
                    "time": ["2025-06-01", "2025-06-02"],
                    "temperature_2m_max": [22.5, 24.0],
                    "temperature_2m_min": [12.0, 13.0],
                    "precipitation_sum": [1.5, 0.0],
                }
            }
        if "api.worldbank.org" in url:
            code = url.split("/country/")[1].split("/")[0].upper()
            return [
                {"page": 1, "total": 1},
                [{"value": 1.1, "date": "2021", "country": {"id": code, "value": code}}],
            ]
        if "TravelAdvisories" in url or "cadataapi.state.gov" in url:
            return {
                "data": [
                    {
                        "country_code": code,
                        "country": name,
                        "level": level,
                        "summary": summary,
                        "updated": "2026-01-15",
                        "url": "https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories.html",
                    }
                    for code, (name, level, summary) in _ADVISORIES.items()
                ]
            }
        if "query.wikidata.org" in url:
            return _wikidata(params.get("query", ""))
        if "wikipedia.org" in url:
            slug = url.rstrip("/").rsplit("/", 1)[-1]
            return {
                "title": slug.replace("_", " "),
                "extract": "Tourism is a major part of the published economy in this country.",
                "content_urls": {"desktop": {"page": f"https://en.wikipedia.org/wiki/{slug}"}},
            }
        raise HttpError(f"no fixture for {url}")

    def post_json(self, url: str, payload: dict, headers: dict | None = None):
        raise HttpError(f"fixture client does not post to {url}")


def _wikidata(query: str) -> dict:
    codes = re.findall(r'P297 "([A-Z]{2})"', query)
    code = codes[0] if codes else "XX"
    if "P2852" in query:
        return {"results": {"bindings": [{"phone": {"value": "112"}}]}}
    if "Q3917681" in query:
        origin = codes[1] if len(codes) > 1 else "US"
        return {
            "results": {
                "bindings": [
                    {
                        "missionLabel": {"value": f"{origin} embassy in {code}"},
                    }
                ]
            }
        }
    if "Q9259" in query:
        label = f"{code} heritage site"
    elif "Q570116" in query:
        label = f"{code} museum"
    elif "Q622425" in query or "Q53060" in query:
        label = f"{code} nightclub"
    else:
        label = f"{code} place"
    return {
        "results": {
            "bindings": [
                {
                    "itemLabel": {"value": label},
                    "article": {"value": f"https://en.wikipedia.org/wiki/{label.replace(' ', '_')}"},
                }
            ]
        }
    }
