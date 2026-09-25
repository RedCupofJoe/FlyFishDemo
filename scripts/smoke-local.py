#!/usr/bin/env python3
"""Generate a two-country guide with fixture sources and ask one follow-up."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for relative in (
    "components/flyfish-common/src",
    "components/mcp/src",
    "components/agents/src",
    "components/indexer/src",
):
    sys.path.insert(0, str(ROOT / relative))

from flyfish_common.memory import MemoryKind, RecordingMemory
from flyfish_common.models import Country, TripRequest
from flyfish_common.store import FileArtifactStore
from flyfish_agents.planner import plan_trip
from flyfish_agents.retrieve import answer_from_guide
from flyfish_agents.tools import ToolCaller
from flyfish_mcp.fixtures import FixtureClient


def main() -> None:
    root = Path("/tmp/flyfish-smoke")
    store = FileArtifactStore(root)
    memory = RecordingMemory()
    request = TripRequest(
        trip_id="smoke",
        countries=(Country("FR", "France"), Country("JP", "Japan")),
        start_date="2026-06-01",
        end_date="2026-06-08",
        season="summer",
        origin=Country("US", "United States"),
        citizenship_status="citizen",
        prompt="Trains, museums, and emergency numbers.",
        user_id="ada",
    )
    guide = plan_trip(request, ToolCaller(http=FixtureClient(), urls={}), memory, store, fixture_mode=True)
    answer = answer_from_guide(guide["markdown"], "What emergency numbers are listed?")
    kinds = sorted({record.kind.value for record in memory.records})
    print(f"guide_bytes {len(guide['markdown'])}")
    print(f"memory_kinds {','.join(kinds)}")
    print(f"follow_up_heading {answer['heading']}")
    print(f"artifact {root / 'trips' / 'smoke' / 'guide.md'}")
    if kinds != ["episodic", "personal", "semantic"]:
        raise SystemExit("expected personal, episodic, and semantic memory")
    if "112" not in answer["content"]:
        raise SystemExit("follow-up did not quote the emergency section")
    if "France" not in guide["markdown"] or guide["markdown"].index("France") > guide["markdown"].index("Japan"):
        raise SystemExit("route order was not preserved")


if __name__ == "__main__":
    main()
