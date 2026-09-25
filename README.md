# FlyFish

FlyFish is an OpenShift 4.20 and OpenShift AI 3.5 demonstration. A traveler picks countries in route order, and specialist agents write a sourced travel guide. A response agent answers follow-up questions from that guide.

The guide covers seasonal weather, travel advisories, crime statistics, landmarks, attractions, nightlife, published tourism context, emergency numbers, and embassies for the traveler's origin country.

## Layout

- `components/flyfish-common` shared report, memory, and storage code
- `components/mcp` one MCP tool per server
- `components/agents` planner, specialists, guide composer, and response agent
- `components/ui` PatternFly map and chat
- `deploy/ai` and `deploy/ui` the two application namespaces
- `deploy/openshell` sandbox policies
- `deploy/prerequisites` cluster-admin steps that are not part of the app namespaces
- `docs/architecture.md` and `docs/demo.md`

## Local checks

```bash
make test
make test-ui
make smoke
```

Cluster install, image builds, and the AutoRAG run are in [docs/demo.md](docs/demo.md). Platform components such as MaaS, OGX, Memory Hub, and OpenShell are prerequisites; this repo does not install them.

Application code is Apache-2.0. License notes are in [docs/licenses.md](docs/licenses.md).
