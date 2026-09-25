import os

from flyfish_agents.catalog import AGENTS
from flyfish_agents.runtime import serve

def main() -> None:
    agent = os.environ.get("FLYFISH_AGENT", "")
    if agent not in AGENTS:
        names = ", ".join(sorted(AGENTS))
        raise SystemExit(f"Set FLYFISH_AGENT to one of: {names}")
    serve(agent)


if __name__ == "__main__":
    main()
