# FlyFish plan

FlyFish is a travel-guide demo on OpenShift 4.20+ and OpenShift AI 3.5. The UI lives in `flyfish-ui`. Agents, MCP servers, SeaweedFS, and pgvector live in `flyfish-ai`. Memory Hub stays on the namespaces created by its upstream installer.

Platform objects:

- MCP catalog: one `MCPServer` per tool.
- Agent catalog: one Deployment per agent, enrolled with `AgentRuntime`, card at `/.well-known/agent-card.json`.
- Reasoning: `RedHatAI/gpt-oss-20b` through the Guardrails Gateway. Granite Guardian stays the detector.
- Sandboxes: OpenShell policies in `deploy/openshell/`.
- Memory: upstream Memory Hub. Personal, episodic, and semantic are metadata kinds, mapped in `.memoryhub.yaml`.
- RAG: one AutoRAG run, then OGX `file_search` for later questions. Without OGX, the response agent quotes the stored guide.
- Observability: OpenTelemetry to the OpenShift AI collector (Tempo) and to MLflow experiment `flyfish-agents`.

Cluster proof is PARTIAL until an admin can log in and the platform secrets exist. See `STATUS.md` and `ISSUES.md`.
