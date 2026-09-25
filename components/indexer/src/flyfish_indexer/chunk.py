"""Split a guide into heading-sized chunks for indexing."""

from __future__ import annotations

import hashlib


def chunk_markdown(markdown: str, *, max_chars: int = 1200) -> list[dict]:
    sections: list[tuple[str, list[str]]] = []
    heading = "Report"
    body: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("#"):
            if body:
                sections.append((heading, body))
            heading = line.lstrip("#").strip()
            body = []
        else:
            body.append(line)
    if body:
        sections.append((heading, body))
    chunks = []
    for heading, lines in sections:
        text = "\n".join(lines).strip()
        if not text:
            continue
        start = 0
        while start < len(text):
            piece = text[start : start + max_chars]
            digest = hashlib.sha256(f"{heading}\n{piece}".encode()).hexdigest()[:16]
            chunks.append({"id": digest, "heading": heading, "content": piece})
            start += max_chars
    return chunks


INDEX_SQL = """
CREATE TABLE IF NOT EXISTS flyfish_artifact_index (
  id TEXT PRIMARY KEY,
  trip_id TEXT NOT NULL,
  source_key TEXT NOT NULL,
  heading TEXT NOT NULL,
  content TEXT NOT NULL,
  autorag_pattern TEXT,
  indexed_at TIMESTAMPTZ DEFAULT NOW()
);
""".strip()


def index_rows(trip_id: str, source_key: str, markdown: str, pattern: str | None) -> list[dict]:
    rows = []
    for chunk in chunk_markdown(markdown):
        rows.append(
            {
                "id": f"{trip_id}:{chunk['id']}",
                "trip_id": trip_id,
                "source_key": source_key,
                "heading": chunk["heading"],
                "content": chunk["content"],
                "autorag_pattern": pattern,
            }
        )
    return rows
