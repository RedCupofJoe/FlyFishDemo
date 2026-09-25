# Status

Implementation of the application, manifests, and docs is in the repo. Live cluster proof is **PARTIAL**. See `ISSUES.md`.

| Area | State |
| --- | --- |
| `flyfish-common` (MaaS client, memory kinds, artifacts, citations, tracing) | Present, covered by pytest |
| Nine MCP servers, one tool each, `MCPServer` manifests | Present |
| Seven agents, A2A cards, OpenShell policies, `AgentRuntime` | Present |
| SeaweedFS, pgvector, AutoRAG seed, indexer CronJob | Present. ODF claim is optional and not in the default kustomize |
| PatternFly UI (map, dates, season, origin, citizenship, chat) | Present, covered by vitest |
| MLflow and OpenTelemetry wiring | Present in `flyfish-platform` and `deploy/ai/observability.yaml` |
| `kustomize build` for `deploy/ai` and `deploy/ui` | Run locally |
| Cluster apply, Memory Hub smoke, bucket guide, browser pass | Not run |

Local checks recorded on 2026-09-24:

- `pytest`: 31 passed
- UI `vitest`: 8 passed
- `scripts/smoke-local.py`: guide written, memory kinds `episodic,personal,semantic`, follow-up heading `Emergency services`
- `kubectl kustomize`: 90 resources in `deploy/ai`, 7 in `deploy/ui`
- Images: `localhost/flyfish-weather-mcp:0.1.0`, `localhost/flyfish-response-agent:0.1.0`, `localhost/flyfish-ui:0.1.0`

```bash
make test
make test-ui
make smoke
make kustomize
```
