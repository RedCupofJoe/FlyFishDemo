"""Specialist skills. Each agent calls only the MCP tools for its role."""

from __future__ import annotations

import json

from flyfish_common.artifacts import render_section, section_key
from flyfish_common.maas import grounded_summary
from flyfish_common.memory import MemoryKind, memory_record
from flyfish_common.models import NOT_LEGAL_ADVICE, Country, Section, TripRequest

SKILLS = {
    "weather": ["weather"],
    "risk": ["travel_advisory", "crime_statistics"],
    "places": ["landmarks", "attractions", "nightlife", "trends"],
    "consular": ["emergency", "embassy"],
}


def country_arguments(request: TripRequest, country: Country) -> dict:
    return {
        "country_name": country.name,
        "country_code": country.code,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "season": request.season,
        "origin_country_name": request.origin.name,
        "origin_country_code": request.origin.code,
    }


def run_skill(
    skill: str,
    request: TripRequest,
    country: Country,
    tools,
    memory,
    store,
    maas_config=None,
    maas_transport=None,
) -> list[Section]:
    sections: list[Section] = []
    for tool_name in SKILLS[skill]:
        result = tools.call(tool_name, country_arguments(request, country))
        result.summary = grounded_summary(result, maas_config, maas_transport)
        section = result.section()
        if skill == "consular" and not section.no_data:
            section.body = f"{section.body}\n\n{NOT_LEGAL_ADVICE}"
        if skill == "consular" and section.no_data:
            section.no_data_reason = f"{section.no_data_reason}\n\n{NOT_LEGAL_ADVICE}"
        sections.append(section)
        markdown = render_section(section)
        store.put_text(section_key(request.trip_id, country.code, tool_name), markdown)
        fact = section.no_data_reason if section.no_data else section.body.split("\n", 1)[0]
        memory.write(
            memory_record(
                MemoryKind.SEMANTIC,
                f"{country.name}: {section.heading}: {fact[:500]}",
                user_id=request.user_id,
                trip_id=request.trip_id,
                country_code=country.code,
                topic=tool_name,
            )
        )
    return sections


def run_specialist(skill: str, request: TripRequest, country: Country, tools, memory, store, maas_config=None, maas_transport=None) -> dict:
    sections = run_skill(skill, request, country, tools, memory, store, maas_config, maas_transport)
    return {
        "country": country.as_dict(),
        "skill": skill,
        "sections": [section.as_dict() for section in sections],
    }


def section_from_dict(payload: dict) -> Section:
    from flyfish_common.models import Citation

    return Section(
        heading=payload["heading"],
        body=payload["body"],
        citations=[Citation(**item) for item in payload["citations"]],
        no_data=payload["no_data"],
        no_data_reason=payload["no_data_reason"],
    )


def decode_task(payload: dict) -> tuple[TripRequest, Country]:
    request = TripRequest.from_dict(payload["trip"])
    country = Country(code=payload["country"]["code"], name=payload["country"]["name"])
    return request, country


def encode_sections(sections: list[Section]) -> str:
    return json.dumps([section.as_dict() for section in sections])
