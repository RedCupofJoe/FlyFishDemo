"""Rules for what a report section is allowed to claim."""

from __future__ import annotations

from flyfish_common.models import CitationError, Section


def validate_section(section: Section) -> None:
    if not section.heading.strip():
        raise CitationError("A section needs a heading.")
    if not section.citations:
        raise CitationError(f"{section.heading} needs a citation or an explicit source gap.")
    for citation in section.citations:
        if not citation.url.startswith(("http://", "https://")):
            raise CitationError(f"{section.heading} has a citation without an http(s) URL.")
        if not citation.retrieved_at:
            raise CitationError(f"{section.heading} has a citation without a retrieval date.")
    if section.no_data:
        if not section.no_data_reason.strip():
            raise CitationError(f"{section.heading} must say which source had no data.")
        return
    if not section.body.strip():
        raise CitationError(f"{section.heading} has no body.")
