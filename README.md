# FlyFish

FlyFish is an OpenShift 4.20 and OpenShift AI 3.5 demonstration. A traveler picks countries in route order, and specialist agents write a sourced travel guide. A response agent answers follow-up questions from that guide.

The guide covers seasonal weather, travel advisories, crime statistics, landmarks, attractions, nightlife, published tourism context, emergency numbers, and embassies for the traveler's origin country.

## Deploy

Log in first. `oc whoami` must succeed. These commands apply only the FlyFish namespaces. They do not install OpenShift AI, Memory Hub, or operators.

Cluster builds clone `https://github.com/RedCupofJoe/FlyFishDemo.git` at `main`. Push this repo to that branch before starting the builds, or the images will not contain this code.

1. Confirm the platform pieces in [deploy/prerequisites/README.md](deploy/prerequisites/README.md): OpenShift 4.20+, OpenShift AI 3.5, the MCP Lifecycle Operator, the agents operator, MaaS for `RedHatAI/gpt-oss-20b` behind Granite Guardrails, and tracing plus MLflow if you want agent traces.
2. From this repository, create the two application namespaces and their workloads:

```bash
oc apply -k deploy/ai
oc apply -k deploy/ui
```

`scripts/bootstrap-cluster.sh` runs those two applies and, when the pipeline CRD exists, also applies `deploy/prerequisites/dspa.yaml`.

3. Build every image. Builds in `flyfish-ai` are the MCP servers and agents. The UI build is in `flyfish-ui`.

```bash
oc get buildconfig -n flyfish-ai -o name | xargs -n1 oc start-build -n flyfish-ai --follow
oc start-build flyfish-ui -n flyfish-ui --follow
```

4. After the ImageStreams have tags, restart the workloads so they pull `0.1.0`:

```bash
oc rollout restart deployment -n flyfish-ai
oc rollout restart deployment -n flyfish-ui
oc rollout status deployment/response-agent -n flyfish-ai
oc rollout status deployment/flyfish-ui -n flyfish-ui
```

5. Create the bucket once `response-agent` is running:

```bash
oc create job flyfish-create-bucket-$(date +%s) -n flyfish-ai --from=job/flyfish-create-bucket
```

6. Point the app at the platform endpoints you actually have. Do not invent keys. Leave a value empty when that component is not installed. The report still generates from tool output, and follow-up answers quote the stored guide.

```bash
oc create secret generic flyfish-maas -n flyfish-ai --from-literal=apiKey="$MAAS_API_KEY"
oc create secret generic flyfish-memoryhub -n flyfish-ai --from-literal=apiKey="$MEMORYHUB_API_KEY"
oc create secret generic flyfish-ogx -n flyfish-ai --from-literal=apiKey="$OGX_API_KEY"

oc set data configmap/flyfish-platform -n flyfish-ai \
  maasBaseUrl="$MAAS_BASE_URL" \
  ogxBaseUrl="$OGX_BASE_URL" \
  ogxVectorStoreId="$OGX_VECTOR_STORE_ID" \
  autoragPatternId="$AUTORAG_PATTERN_ID"
oc rollout restart deployment -n flyfish-ai
```

Memory Hub itself is installed from its upstream repository, in its own namespaces: `git clone https://github.com/redhat-ai-americas/memory-hub.git && cd memory-hub && make install`.

7. Replace `maas-gateway.example.svc` and `ogx.example.svc` in `deploy/openshell/` with the real Service hostnames, then load each policy with `openshell policy set`.
8. Open the UI:

```bash
oc get route flyfish -n flyfish-ui
```

Select two countries in travel order, set origin, citizenship, dates, and a prompt, generate the guide, then ask about a section that appears in it.

AutoRAG seed files, the indexer job, and trace lookup are in [docs/demo.md](docs/demo.md).

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

Application code is Apache-2.0. License notes are in [docs/licenses.md](docs/licenses.md).
