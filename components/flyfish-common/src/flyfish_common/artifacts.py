"""Markdown artifacts stored for AutoRAG and follow-up answers."""

from __future__ import annotations

from flyfish_common.citations import validate_section
from flyfish_common.models import NOT_LEGAL_ADVICE, Country, Section, TripRequest


def country_key(trip_id: str, country_code: str) -> str:
    return f"trips/{trip_id}/{country_code}.md"


def section_key(trip_id: str, country_code: str, skill: str) -> str:
    return f"trips/{trip_id}/{country_code}-{skill}.md"


def guide_key(trip_id: str) -> str:
    return f"trips/{trip_id}/guide.md"


def request_key(trip_id: str) -> str:
    return f"trips/{trip_id}/request.json"


def render_section(section: Section) -> str:
    validate_section(section)
    lines = [f"### {section.heading}", ""]
    if section.no_data:
        lines.append(section.no_data_reason.strip())
    else:
        lines.append(section.body.strip())
    lines.append("")
    lines.append("Sources:")
    for citation in section.citations:
        lines.append(f"- {citation.title} ({citation.retrieved_at}): {citation.url}")
    lines.append("")
    return "\n".join(lines)


def render_country(
    country: Country,
    sections: list[Section],
    *,
    fixture_mode: bool = False,
) -> str:
    lines = [f"## {country.name}", ""]
    if fixture_mode:
        lines.append(
            "Source mode: fixture responses for an offline demonstration. "
            "Do not use these figures for travel decisions."
        )
        lines.append("")
    for section in sections:
        lines.append(render_section(section))
    return "\n".join(lines).rstrip() + "\n"


def render_guide(
    request: TripRequest,
    country_markdown: list[str],
    *,
    fixture_mode: bool = False,
) -> str:
    route = " → ".join(country.name for country in request.countries)
    lines = [
        f"# FlyFish travel guide: {route}",
        "",
        f"Trip: {request.trip_id}",
        f"Dates: {request.start_date} to {request.end_date} ({request.season})",
        f"Country of origin: {request.origin.name} ({request.origin.code})",
        f"Citizenship status: {request.citizenship_status.replace('_', ' ')}",
        f"Traveler prompt: {request.prompt.strip()}",
        "",
        NOT_LEGAL_ADVICE,
        "",
    ]
    if fixture_mode:
        lines.extend(
            [
                "Source mode: fixture responses for an offline demonstration. "
                "Do not use these figures for travel decisions.",
                "",
            ]
        )
    lines.append(f"Route order: {route}")
    lines.append("")
    for markdown in country_markdown:
        lines.append(markdown.rstrip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
