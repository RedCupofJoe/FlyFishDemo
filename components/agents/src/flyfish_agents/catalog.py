"""Agent catalog metadata served at /.well-known/agent-card.json."""

from __future__ import annotations

AGENTS = {
    "planner": {
        "name": "flyfish-planner",
        "description": "Orders the selected countries and fans out specialist agents.",
        "skills": [{"id": "plan-trip", "name": "Plan a trip report", "description": "Collect specialist sections for each country in route order.", "tags": ["planning"]}],
    },
    "weather": {
        "name": "flyfish-weather",
        "description": "Writes the weather section from the weather MCP server.",
        "skills": [{"id": "seasonal-weather", "name": "Seasonal weather", "description": "Archived weather for the trip dates.", "tags": ["weather"]}],
    },
    "risk": {
        "name": "flyfish-risk",
        "description": "Writes travel-advisory and crime-statistics sections.",
        "skills": [
            {"id": "travel-advisory", "name": "Travel advisory", "description": "Advisory level and summary.", "tags": ["safety"]},
            {"id": "crime-statistics", "name": "Crime statistics", "description": "National homicide rate.", "tags": ["safety"]},
        ],
    },
    "places": {
        "name": "flyfish-places",
        "description": "Writes landmarks, attractions, nightlife, and tourism-context sections.",
        "skills": [
            {"id": "landmarks", "name": "Landmarks", "description": "World Heritage sites.", "tags": ["places"]},
            {"id": "attractions", "name": "Tourist attractions", "description": "Wikidata attractions.", "tags": ["places"]},
            {"id": "nightlife", "name": "Nightlife", "description": "Nightclubs and bars.", "tags": ["places"]},
            {"id": "trends", "name": "Travel context", "description": "Wikipedia tourism summary.", "tags": ["places"]},
        ],
    },
    "consular": {
        "name": "flyfish-consular",
        "description": "Writes emergency-number and embassy sections for the traveler's citizenship context.",
        "skills": [
            {"id": "emergency", "name": "Emergency services", "description": "Emergency telephone numbers.", "tags": ["consular"]},
            {"id": "embassy", "name": "Embassies", "description": "Missions of the origin country.", "tags": ["consular"]},
        ],
    },
    "guide": {
        "name": "flyfish-guide",
        "description": "Combines per-country artifacts into one travel guide.",
        "skills": [{"id": "compose-guide", "name": "Compose travel guide", "description": "Merge country reports in route order.", "tags": ["guide"]}],
    },
    "response": {
        "name": "flyfish-response",
        "description": "UI entrypoint. Generates a guide, then answers questions from the indexed report.",
        "skills": [
            {"id": "generate-report", "name": "Generate report", "description": "Delegate a new trip to the planner.", "tags": ["chat"]},
            {"id": "answer-report", "name": "Answer from the report", "description": "Ground follow-up answers in the guide.", "tags": ["rag"]},
        ],
    },
}


def agent_card(agent: str, url: str) -> dict:
    spec = AGENTS[agent]
    return {
        "name": spec["name"],
        "description": spec["description"],
        "url": url,
        "version": "0.1.0",
        "protocolVersion": "0.3.0",
        "capabilities": {"streaming": False},
        "skills": spec["skills"],
        "defaultInputModes": ["application/json", "text/plain"],
        "defaultOutputModes": ["text/markdown", "application/json"],
    }
