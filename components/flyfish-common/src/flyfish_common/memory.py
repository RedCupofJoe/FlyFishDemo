"""Map FlyFish memory kinds onto Memory Hub scopes.

Memory Hub stores scopes (user, project, role, organizational, enterprise).
FlyFish keeps the three kinds the demo asks for as metadata on those scopes:

- personal: user scope, the traveler's origin and citizenship
- episodic: project scope, what this trip's agents did
- semantic: project scope, country facts reused on later trips
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class MemoryKind(str, Enum):
    PERSONAL = "personal"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


_SCOPE = {
    MemoryKind.PERSONAL: "user",
    MemoryKind.EPISODIC: "project",
    MemoryKind.SEMANTIC: "project",
}
_WEIGHT = {
    MemoryKind.PERSONAL: 0.9,
    MemoryKind.EPISODIC: 0.8,
    MemoryKind.SEMANTIC: 0.7,
}


@dataclass(frozen=True)
class MemoryRecord:
    kind: MemoryKind
    content: str
    scope: str
    weight: float
    metadata: dict

    def write_arguments(self) -> dict:
        return {
            "content": self.content,
            "scope": self.scope,
            "weight": self.weight,
            "metadata": self.metadata,
        }


def memory_record(
    kind: MemoryKind,
    content: str,
    *,
    user_id: str,
    trip_id: str | None = None,
    country_code: str | None = None,
    topic: str | None = None,
) -> MemoryRecord:
    metadata = {"kind": kind.value, "project": "flyfish", "user_id": user_id}
    if trip_id:
        metadata["trip_id"] = trip_id
    if country_code:
        metadata["country_code"] = country_code
    if topic:
        metadata["topic"] = topic
    return MemoryRecord(
        kind=kind,
        content=content,
        scope=_SCOPE[kind],
        weight=_WEIGHT[kind],
        metadata=metadata,
    )


class MemoryClient(Protocol):
    def write(self, record: MemoryRecord) -> str: ...

    def search(self, query: str, kind: MemoryKind | None = None) -> list[dict]: ...


class RecordingMemory:
    """In-process memory used when Memory Hub is not configured."""

    def __init__(self) -> None:
        self.records: list[MemoryRecord] = []

    def write(self, record: MemoryRecord) -> str:
        self.records.append(record)
        return f"local-{len(self.records)}"

    def search(self, query: str, kind: MemoryKind | None = None) -> list[dict]:
        terms = query.lower().split()
        matches = []
        for record in self.records:
            if kind is not None and record.kind is not kind:
                continue
            haystack = record.content.lower()
            if not terms or all(term in haystack for term in terms):
                matches.append({"content": record.content, "metadata": record.metadata})
        return matches


class MemoryHubClient:
    """Call Memory Hub's MCP tools: register_session, write_memory, search_memory."""

    def __init__(self, transport, api_key: str) -> None:
        self.transport = transport
        self.api_key = api_key
        self._registered = False
        self._next_id = 1

    def write(self, record: MemoryRecord) -> str:
        self._ensure_session()
        return self._tool("write_memory", record.write_arguments())

    def search(self, query: str, kind: MemoryKind | None = None) -> list[dict]:
        self._ensure_session()
        arguments: dict = {"query": query, "max_results": 8, "focus": "FlyFish travel"}
        if kind is MemoryKind.PERSONAL:
            arguments["scope"] = "user"
        elif kind is not None:
            arguments["scope"] = "project"
        payload = self._tool("search_memory", arguments)
        if isinstance(payload, dict):
            results = payload.get("results", [])
            if kind is None:
                return results
            return [item for item in results if item.get("metadata", {}).get("kind") == kind.value]
        return []

    def _ensure_session(self) -> None:
        if self._registered:
            return
        self._tool("register_session", {"api_key": self.api_key})
        self._registered = True

    def _tool(self, name: str, arguments: dict):
        message = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        self._next_id += 1
        response = self.transport.request(message)
        result = response.get("result", {})
        if result.get("isError"):
            raise RuntimeError(f"Memory Hub tool {name} failed")
        content = result.get("content") or []
        if not content:
            return result
        text = content[0].get("text", "")
        if text.startswith("{") or text.startswith("["):
            import json

            return json.loads(text)
        return text
