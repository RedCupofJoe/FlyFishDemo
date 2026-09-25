# Issues

Cluster completion is **PARTIAL**. These items are not worked around with invented credentials.

## No cluster login

`oc whoami` cannot reach the API host in the current kubeconfig (`api.cluster-8bvp8.8bvp8.sandbox3925.opentlc.com` did not resolve). Manifests were not applied. Do not treat a local fixture run as a cluster deploy.

## Platform secrets are unset

These Secrets are optional in the Deployments and are not created by the repo:

- `flyfish-maas` key `apiKey` (Guardrails Gateway)
- `flyfish-memoryhub` key `apiKey`
- `flyfish-ogx` key `apiKey`

`flyfish-platform` leaves `maasBaseUrl`, `ogxBaseUrl`, and `ogxVectorStoreId` empty until an admin fills them. Without `MAAS_BASE_URL`, agents keep the tool summary. Without OGX, follow-up answers quote the stored guide.

## Platform components are not installed by FlyFish

Still required from an admin: MCP Lifecycle Operator, the agents operator, MaaS publication of `RedHatAI/gpt-oss-20b`, Granite Guardian on TrustyAI, OGX, a pipeline server with AutoRAG, OpenShell, upstream Memory Hub, DSCInitialization tracing, and the MLflow custom resource in `deploy/prerequisites/mlflow.yaml`.

## Images

Built locally: `localhost/flyfish-weather-mcp:0.1.0`, `localhost/flyfish-response-agent:0.1.0`, and `localhost/flyfish-ui:0.1.0`. The other MCP servers use the same MCP Containerfile with a different `FLYFISH_TOOL` build arg. Their ImageStreams are produced on the cluster with `oc start-build`. The agent image includes the OpenTelemetry packages from `requirements-agents.txt`.

## pgvector on restricted-v2

`pgvector/pgvector:pg16` and SeaweedFS may fail the restricted-v2 SCC if their entrypoints require root. The manifests set `runAsNonRoot`, drop all capabilities, and use `RuntimeDefault` seccomp. Confirm both pods become Ready after apply.

## UI browser pass

Local fixture chat for trip `ui-smoke-2` returned a guide (France before Japan) and a follow-up that included the fixture emergency number 112. A full browser click-through of the map was not completed on the cluster, because the cluster is not reachable.
