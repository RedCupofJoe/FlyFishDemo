"""Build the OGX vector-store attach request used after AutoRAG selects a pattern."""

from __future__ import annotations


def vector_store_file_body(file_id: str) -> dict:
    return {"file_id": file_id}


def responses_index_note(pattern_id: str, source_key: str) -> str:
    return (
        f"Index {source_key} with AutoRAG pattern {pattern_id}. "
        "The pattern was chosen by one optimization run; this upload does not start a new search."
    )
