"""Fan out specialist skills in route order and compose the guide."""

from __future__ import annotations

import json

from flyfish_common.artifacts import country_key, guide_key, render_country, render_guide, request_key
from flyfish_common.telemetry import span
from flyfish_common.memory import MemoryKind, memory_record
from flyfish_common.models import Country, Section, TripRequest, validate_trip
from flyfish_agents.specialists import run_skill, section_from_dict

SKILL_ORDER = ("weather", "risk", "places", "consular")


class RemoteSkills:
    """Call specialist agent Deployments when their URLs are configured."""

    def __init__(self, http, urls: dict[str, str]) -> None:
        self.http = http
        self.urls = urls

    def run(self, skill: str, request: TripRequest, country: Country) -> list[Section]:
        base = self.urls.get(skill, "")
        if not base:
            raise RuntimeError(f"No URL for {skill}")
        response = self.http.post_json(
            f"{base}/v1/tasks",
            {"trip": request.as_dict(), "country": country.as_dict()},
        )
        return [section_from_dict(item) for item in response["sections"]]

    def compose(self, request: TripRequest, country_markdown: list[str], fixture_mode: bool) -> str:
        base = self.urls["guide"]
        response = self.http.post_json(
            f"{base}/v1/tasks",
            {
                "trip": request.as_dict(),
                "country_markdown": country_markdown,
                "fixture_mode": fixture_mode,
            },
        )
        return response["markdown"]


def plan_trip(request: TripRequest, tools, memory, store, remote: RemoteSkills | None = None, maas_config=None, maas_transport=None, fixture_mode: bool = False) -> dict:
    errors = validate_trip(request)
    if errors:
        raise ValueError("; ".join(errors))
    store.put_text(request_key(request.trip_id), json.dumps(request.as_dict(), indent=2), "application/json")
    memory.write(
        memory_record(
            MemoryKind.PERSONAL,
            (
                f"Traveler {request.user_id} origin is {request.origin.name} ({request.origin.code}) "
                f"and citizenship status is {request.citizenship_status}."
            ),
            user_id=request.user_id,
            trip_id=request.trip_id,
            topic="traveler-profile",
        )
    )
    country_markdown: list[str] = []
    for country in request.countries:
        sections: list[Section] = []
        for skill in SKILL_ORDER:
            with span(
                "flyfish.skill",
                {
                    "flyfish.skill": skill,
                    "flyfish.country": country.code,
                    "flyfish.trip_id": request.trip_id,
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.agent.name": f"{skill}-agent",
                },
            ):
                if remote and remote.urls.get(skill):
                    sections.extend(remote.run(skill, request, country))
                else:
                    sections.extend(
                        run_skill(
                            skill,
                            request,
                            country,
                            tools,
                            memory,
                            store,
                            maas_config,
                            maas_transport,
                        )
                    )
        markdown = render_country(country, sections, fixture_mode=fixture_mode)
        store.put_text(country_key(request.trip_id, country.code), markdown)
        country_markdown.append(markdown)
        memory.write(
            memory_record(
                MemoryKind.EPISODIC,
                (
                    f"Trip {request.trip_id} collected {', '.join(SKILL_ORDER)} for {country.name} "
                    f"in route position {request.countries.index(country) + 1}."
                ),
                user_id=request.user_id,
                trip_id=request.trip_id,
                country_code=country.code,
                topic="country-complete",
            )
        )
    with span(
        "flyfish.guide",
        {
            "flyfish.trip_id": request.trip_id,
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "guide-agent",
        },
    ):
        if remote and remote.urls.get("guide"):
            guide = remote.compose(request, country_markdown, fixture_mode)
        else:
            guide = render_guide(request, country_markdown, fixture_mode=fixture_mode)
    store.put_text(guide_key(request.trip_id), guide)
    memory.write(
        memory_record(
            MemoryKind.EPISODIC,
            f"Trip {request.trip_id} guide written for route {' -> '.join(c.name for c in request.countries)}.",
            user_id=request.user_id,
            trip_id=request.trip_id,
            topic="guide-written",
        )
    )
    return {"trip_id": request.trip_id, "markdown": guide}
