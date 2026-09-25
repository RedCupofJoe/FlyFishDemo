"""OpenAI-compatible client for the Guardrails Gateway in front of MaaS.

The default model is the strongest reasoning model in the OpenShift AI 3.5
catalog that Red Hat validates on one NVIDIA L4: ``RedHatAI/gpt-oss-20b``
(16 GB). Granite Guardian stays on the gateway as the safety detector; it is
not the reasoning model.

When MAAS_BASE_URL is unset, callers keep the tool summary. A configured
endpoint may rewrite that summary, but only when every number in the rewrite
already appears in the tool payload.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from flyfish_common.grounding import prose_is_grounded
from flyfish_common.models import ToolResult
from flyfish_common.telemetry import span

# Catalog id. Modelcar: oci://registry.redhat.io/rhelai1/modelcar-gpt-oss-20b:1.5
REASONING_MODEL = "RedHatAI/gpt-oss-20b"
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class MaasConfig:
    base_url: str
    api_key: str
    model: str

    @classmethod
    def from_env(cls) -> "MaasConfig | None":
        base_url = os.environ.get("MAAS_BASE_URL", "").rstrip("/")
        if not base_url:
            return None
        return cls(
            base_url=base_url,
            api_key=os.environ.get("MAAS_API_KEY", ""),
            model=os.environ.get("MAAS_MODEL", REASONING_MODEL),
        )


def visible_prose(message: dict) -> str:
    """Drop a reasoning trace. The travel paragraph is the final answer only."""
    content = message.get("content") or ""
    if not isinstance(content, str):
        content = str(content)
    return _THINK.sub("", content).strip()


def grounded_summary(result: ToolResult, config: MaasConfig | None, transport=None) -> str:
    if config is None or transport is None or result.no_data:
        return result.summary
    source = json.dumps(result.as_dict(), sort_keys=True)
    payload = {
        "model": config.model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Reasoning: high\n"
                    "Rewrite the tool summary as a short travel paragraph. "
                    "Use only facts present in the JSON. Do not add numbers, "
                    "place names, phone numbers, or procedures that are not in the JSON."
                ),
            },
            {"role": "user", "content": source},
        ],
    }
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    with span(
        "gen_ai.chat",
        {
            "gen_ai.operation.name": "chat",
            "gen_ai.request.model": config.model,
            "gen_ai.provider.name": "maas",
        },
    ):
        response = transport.post_json(f"{config.base_url}/v1/chat/completions", payload, headers=headers)
    prose = visible_prose(response["choices"][0]["message"])
    if not prose_is_grounded(prose, source):
        return result.summary
    return prose
