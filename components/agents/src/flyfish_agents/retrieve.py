"""Answer a follow-up from the generated guide, or from OGX file_search when configured."""

from __future__ import annotations

import os
import re

from flyfish_common.artifacts import guide_key
from flyfish_common.maas import REASONING_MODEL, visible_prose


_STOP = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "what",
    "was",
    "were",
    "are",
    "how",
    "when",
    "where",
    "which",
    "about",
    "into",
    "your",
    "have",
    "has",
}


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2 and token not in _STOP}


def _sections(markdown: str) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    heading = "Report"
    body: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("### "):
            if body:
                chunks.append((heading, "\n".join(body).strip()))
            heading = line[4:].strip()
            body = []
        else:
            body.append(line)
    if body:
        chunks.append((heading, "\n".join(body).strip()))
    return chunks


def answer_from_guide(markdown: str, question: str) -> dict:
    question_terms = _tokens(question)
    best_score = 0
    best: tuple[str, str] | None = None
    for heading, body in _sections(markdown):
        score = len(question_terms & _tokens(body)) + 3 * len(question_terms & _tokens(heading))
        if score > best_score:
            best_score = score
            best = (heading, body)
    if best is None or best_score == 0:
        return {
            "content": "The generated report does not contain that information.",
            "grounded": True,
            "heading": None,
        }
    heading, body = best
    excerpt = body.strip()
    if len(excerpt) > 1200:
        excerpt = excerpt[:1200].rsplit(" ", 1)[0] + "..."
    return {
        "content": f"From the {heading} section of the generated report:\n\n{excerpt}",
        "grounded": True,
        "heading": heading,
    }


def answer_question(store, trip_id: str, question: str, ogx=None) -> dict:
    if ogx is not None:
        remote = ogx.answer(trip_id, question)
        if remote is not None:
            return remote
    markdown = store.get_text(guide_key(trip_id))
    return answer_from_guide(markdown, question)


class OgxFileSearch:
    """OpenShift AI OGX Responses API file_search. Returns None when unset or failed."""

    def __init__(self, http, base_url: str, api_key: str, model: str, vector_store_id: str) -> None:
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.vector_store_id = vector_store_id

    @classmethod
    def from_env(cls, http):
        base_url = os.environ.get("OGX_BASE_URL", "")
        vector_store = os.environ.get("OGX_VECTOR_STORE_ID", "")
        if not base_url or not vector_store:
            return None
        return cls(
            http,
            base_url,
            os.environ.get("OGX_API_KEY", ""),
            os.environ.get("OGX_MODEL", REASONING_MODEL),
            vector_store,
        )

    def answer(self, trip_id: str, question: str) -> dict | None:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "input": (
                "Reasoning: high\n"
                f"Trip {trip_id}. Answer only from retrieved report text.\n\n{question}"
            ),
            "tools": [{"type": "file_search", "vector_store_ids": [self.vector_store_id]}],
        }
        try:
            response = self.http.post_json(f"{self.base_url}/v1/responses", payload, headers=headers)
        except Exception:
            return None
        text = _response_text(response)
        if not text:
            return None
        return {"content": text, "grounded": True, "heading": "AutoRAG", "source": "ogx"}


def _response_text(response: dict) -> str:
    if isinstance(response.get("output_text"), str):
        return visible_prose({"content": response["output_text"]})
    chunks = []
    for item in response.get("output") or []:
        for content in item.get("content") or []:
            text = content.get("text")
            if text:
                chunks.append(text)
    return visible_prose({"content": "\n".join(chunks)})
