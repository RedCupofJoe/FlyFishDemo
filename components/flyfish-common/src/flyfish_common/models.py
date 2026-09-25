"""Trip, citation, and tool-result models.

These are plain dataclasses so the demo runtime stays on the Python standard
library. Agents render only fields that a tool returned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


class CitationError(ValueError):
    """Raised when a report section has no source and no explicit gap."""


@dataclass(frozen=True)
class Citation:
    title: str
    url: str
    retrieved_at: str

    def as_dict(self) -> dict:
        return {"title": self.title, "url": self.url, "retrieved_at": self.retrieved_at}


@dataclass(frozen=True)
class Country:
    code: str
    name: str

    def as_dict(self) -> dict:
        return {"code": self.code, "name": self.name}


@dataclass(frozen=True)
class TripRequest:
    trip_id: str
    countries: tuple[Country, ...]
    start_date: str
    end_date: str
    season: str
    origin: Country
    citizenship_status: str
    prompt: str
    user_id: str = "traveler"

    def as_dict(self) -> dict:
        return {
            "trip_id": self.trip_id,
            "countries": [country.as_dict() for country in self.countries],
            "start_date": self.start_date,
            "end_date": self.end_date,
            "season": self.season,
            "origin": self.origin.as_dict(),
            "citizenship_status": self.citizenship_status,
            "prompt": self.prompt,
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "TripRequest":
        countries = tuple(
            Country(code=item["code"], name=item["name"]) for item in payload["countries"]
        )
        origin = payload["origin"]
        return cls(
            trip_id=payload["trip_id"],
            countries=countries,
            start_date=payload["start_date"],
            end_date=payload["end_date"],
            season=payload["season"],
            origin=Country(code=origin["code"], name=origin["name"]),
            citizenship_status=payload["citizenship_status"],
            prompt=payload["prompt"],
            user_id=payload.get("user_id", "traveler"),
        )


def validate_trip(request: TripRequest, *, today: date | None = None) -> list[str]:
    """Return human-readable problems. An empty list means the trip can run."""
    errors: list[str] = []
    if not request.countries:
        errors.append("Select at least one country.")
    codes = [country.code for country in request.countries]
    if len(codes) != len(set(codes)):
        errors.append("Each country can appear only once in the route.")
    if not request.origin.code:
        errors.append("Select a country of origin.")
    if not request.citizenship_status:
        errors.append("Select a citizenship status.")
    if not request.prompt.strip():
        errors.append("Enter a prompt for the report.")
    if not request.season.strip():
        errors.append("Select a time of year.")
    try:
        start = date.fromisoformat(request.start_date)
        end = date.fromisoformat(request.end_date)
    except ValueError:
        errors.append("Use YYYY-MM-DD dates.")
        return errors
    if end < start:
        errors.append("The end date must be on or after the start date.")
    if today is not None and end < today:
        errors.append("The trip dates are in the past.")
    return errors


@dataclass
class Section:
    heading: str
    body: str
    citations: list[Citation] = field(default_factory=list)
    no_data: bool = False
    no_data_reason: str = ""

    def as_dict(self) -> dict:
        return {
            "heading": self.heading,
            "body": self.body,
            "citations": [citation.as_dict() for citation in self.citations],
            "no_data": self.no_data,
            "no_data_reason": self.no_data_reason,
        }


@dataclass
class ToolResult:
    """Facts a tool actually retrieved. `summary` restates `facts` only."""

    heading: str
    summary: str
    facts: dict
    citations: list[Citation]
    no_data: bool = False
    no_data_reason: str = ""

    def section(self) -> Section:
        return Section(
            heading=self.heading,
            body=self.summary,
            citations=list(self.citations),
            no_data=self.no_data,
            no_data_reason=self.no_data_reason,
        )

    def as_dict(self) -> dict:
        return {
            "heading": self.heading,
            "summary": self.summary,
            "facts": self.facts,
            "citations": [citation.as_dict() for citation in self.citations],
            "no_data": self.no_data,
            "no_data_reason": self.no_data_reason,
        }


NOT_LEGAL_ADVICE = (
    "This section is general information from public sources. It is not legal advice "
    "and does not replace official instructions from the destination country or from "
    "the traveler's own embassy or consulate."
)
