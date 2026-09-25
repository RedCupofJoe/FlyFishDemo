# Run FlyFish

## Local report

This path does not need a cluster. It uses labeled fixture responses instead of live reference sites.

```bash
python3 -m pytest tests -q
cd components/ui && npm test
python3 scripts/smoke-local.py
```

The UI and response agent:

```bash
FLYFISH_USE_FIXTURES=1 FLYFISH_AGENT=response ARTIFACT_DIR=/tmp/flyfish-artifacts \
  PYTHONPATH=components/flyfish-common/src:components/mcp/src:components/agents/src:components/indexer/src \
  python3 -m flyfish_agents
```

In another shell:

```bash
cd components/ui && npm run dev
```

Open the Vite URL. Select France, then Japan. Set an origin, a citizenship status, dates, a time of year, and a prompt. Generate the report, then ask about a section that appears in it, such as emergency numbers.

## Images

Build from the repository root. The Dockerfiles use Red Hat UBI images.

```bash
podman build -f components/mcp/Containerfile --build-arg FLYFISH_TOOL=weather -t flyfish-weather-mcp:0.1.0 .
podman build -f components/agents/Containerfile --build-arg FLYFISH_AGENT=response -t flyfish-response-agent:0.1.0 .
podman build -f components/ui/Containerfile -t flyfish-ui:0.1.0 .
```

## Cluster

Admin steps are in `deploy/prerequisites/README.md`. From a machine logged in with `oc`:

```bash
oc apply -k deploy/ai
oc apply -k deploy/ui
oc start-build weather-mcp -n flyfish-ai --follow
# repeat oc start-build for each ImageStream, or start them all:
oc get buildconfig -n flyfish-ai -o name | xargs -n1 oc start-build -n flyfish-ai --follow
oc start-build flyfish-ui -n flyfish-ui --follow
oc apply -f deploy/prerequisites/dspa.yaml
```

Create the bucket Job after the response-agent image exists:

```bash
oc create job flyfish-create-bucket-$(date +%s) -n flyfish-ai --from=job/flyfish-create-bucket
```

Upload the AutoRAG seed, then start the optimization run in Gen AI Studio → AutoRAG. The evaluation file is `deploy/ai/autorag/eval.json`. The document file name is `seed-guide.md`. After a pattern wins, set `autoragPatternId` and `ogxVectorStoreId` on ConfigMap `flyfish-platform`.

Memory Hub:

```bash
git clone https://github.com/redhat-ai-americas/memory-hub.git
cd memory-hub && make install
oc create secret generic flyfish-memoryhub -n flyfish-ai --from-literal=apiKey="$MEMORYHUB_API_KEY"
```

Smoke on the cluster, after the route exists:

```bash
oc get mcpserver,agentruntime,agentcard -n flyfish-ai
ROUTE=$(oc get route flyfish -n flyfish-ui -o jsonpath='{.spec.host}')
echo "https://${ROUTE}"
```

Generate a two-country report in the UI and ask a follow-up. The same trip is one OpenTelemetry trace. Open the MLflow UI from the OpenShift AI application menu, select workspace `flyfish-ai`, and open experiment `flyfish-agents`. Tempo has the same trace: `oc port-forward svc/tempo-query-frontend 3200:3200 -n redhat-ods-monitoring`.

Reindex a trip with:

```bash
oc create job flyfish-index-trip-1 -n flyfish-ai --from=cronjob/flyfish-index
oc set env job/flyfish-index-trip-1 -n flyfish-ai TRIP_ID=trip-1
```

If `oc` is not logged in, or a secret is missing, stop. The local tests can still pass. Cluster acceptance stays partial until those commands have been run.
