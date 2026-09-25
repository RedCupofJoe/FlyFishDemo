import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for relative in (
    "components/flyfish-common/src",
    "components/mcp/src",
    "components/agents/src",
    "components/indexer/src",
):
    path = str(ROOT / relative)
    if path not in sys.path:
        sys.path.insert(0, path)
