# FlyFish architecture

FlyFish builds a travel guide for an ordered list of countries, then answers questions about that guide. The UI in `flyfish-ui` talks only to the response agent in `flyfish-ai`. The response agent delegates a new trip to the planner. Follow-up questions stay on the response agent.

## Namespaces

- `flyfish-ai` holds agents, MCP servers, SeaweedFS, pgvector, and the AutoRAG pipeline connection.
- `flyfish-ui` holds the web UI and its Route.
- Memory Hub stays on the namespaces created by its upstream installer.
- MaaS, OGX, TrustyAI, the MCP Lifecycle Operator, the agents operator, and the OpenShell gateway stay in their platform namespaces.

## Agents

| Agent | MCP servers | Job |
| --- | --- | --- |
| planner | none | Fans out specialists in route order and asks the guide agent to compose the guide |
| weather | weather | Archived weather for the same dates one year earlier |
| risk | travel advisory, crime statistics | Advisory text and the World Bank homicide rate |
| places | landmarks, attractions, nightlife, trends | Wikidata places and a Wikipedia tourism summary |
| consular | emergency, embassy | Emergency numbers and the origin country's missions |
| guide | none | One guide in route order |
| response | none | UI entrypoint and follow-up answers |

Each MCP server is its own container and its own `MCPServer` custom resource. Each agent is a Deployment enrolled with `AgentRuntime`. The A2A card is `/.well-known/agent-card.json`.

Agents call `RedHatAI/gpt-oss-20b` only through the Guardrails Gateway (`MAAS_BASE_URL`). That is the strongest reasoning model in the OpenShift AI 3.5 catalog that Red Hat validates on one NVIDIA L4 (16 GB). Granite Guardian on the TrustyAI FMS orchestrator is the safety check in front of that model. If the gateway URL is empty, the report keeps the tool summary. If the model adds a number that was not in the tool payload, that rewrite is discarded. A `<think>` trace is dropped before the grounding check.

OpenShell policies in `deploy/openshell/` limit each agent to Memory Hub, its MCP servers, the artifact bucket, peer agents, the guarded model endpoint, the OpenShift AI OpenTelemetry collector, and the MLflow tracking Service.

## Observability

Each agent emits OpenTelemetry spans for the HTTP request, each specialist skill, the guide composition, outbound HTTP calls, and the guarded model rewrite. A `traceparent` header ties the response agent, planner, and specialists into one trace. Spans record the agent, skill, trip id, and model name. They do not record the traveler prompt or tool payloads.

Two exporters run when their endpoints are set in ConfigMap `flyfish-platform`:

- `otelExporterOtlpEndpoint` sends OTLP/HTTP to the OpenShift AI collector (`data-science-collector.redhat-ods-monitoring.svc.cluster.local:4318`), which stores traces in Tempo.
- `mlflowTrackingUri` sends the same spans to the cluster MLflow server's `/v1/traces` ingest. The experiment is `flyfish-agents` in workspace `flyfish-ai`. Each agent ServiceAccount is bound to the `mlflow-operator-mlflow-integration` ClusterRole and authenticates with its projected token.

Health checks are not traced. If either backend is down, the agent logs the failure and keeps serving.

## Memory

Memory Hub does not have kinds named personal, episodic, and semantic. FlyFish writes those kinds in metadata:

- personal: user scope, origin and citizenship
- episodic: project scope, what happened on this trip
- semantic: project scope, country facts for a later trip

The mapping is in `.memoryhub.yaml`. Without `MEMORYHUB_URL` and `MEMORYHUB_API_KEY`, writes stay in the process that created them.

## Artifacts and RAG

Specialists write Markdown under `trips/{tripId}/`. The guide is `trips/{tripId}/guide.md`. That prefix is the AutoRAG document folder.

One AutoRAG optimization run, using `deploy/ai/autorag/eval.json` and `seed-guide.md`, chooses the RAG pattern. Later trips are indexed with that pattern into pgvector through OGX. The response agent calls the OGX Responses API `file_search` tool when `OGX_BASE_URL` and `OGX_VECTOR_STORE_ID` are set. Otherwise it quotes the stored guide and says when the guide does not contain the answer.

Object storage is SeaweedFS in `flyfish-ai`. An ObjectBucketClaim for OpenShift Data Foundation is in `deploy/ai/odf/`. FlyFish guides use bucket `flyfish-artifacts`. Memory Hub oversized content uses bucket `memoryhub` on the same Service. This lab does not deploy MinIO.

## Report rules

Every section cites an http(s) URL and a retrieval date, or it says which source had no data. Consular sections include a notice that the text is not legal advice. Fixture mode, used for offline tests and the local UI, labels the guide so sample figures are not presented as live travel data.

## UI

The page is a PatternFly React application. The map is simplified Natural Earth geometry (public domain) with ISO codes on each country. The traveler sets route order, dates, time of year, country of origin, and citizenship status. The chat shows the guide and sends follow-up questions to `/api/v1/chat`, which the UI server proxies to the response agent.
