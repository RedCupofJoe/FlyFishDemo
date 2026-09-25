# Platform prerequisites

FlyFish workloads stay in `flyfish-ai` and `flyfish-ui`. These platform pieces are installed by a cluster admin outside those namespaces. The app manifests do not install operators and do not grant privileged SCCs.

## Prerequisite

This lab starts from the cluster at `<CLUSTER_API>` (`oc login <CLUSTER_API>`), before any FlyFish install. The numbered steps below add what that cluster did not already have.

Already present:

- OpenShift 4.21.33 and OpenShift AI 3.5.1. DataScienceCluster `default-dsc` is Ready.
- Pipelines, KServe, TrustyAI, the MaaS controller, the MLflow operator, and the OGX operator are Managed.
- The OpenTelemetry collector and Tempo are running in `redhat-ods-monitoring`. Trace storage is a persistent volume with retention `2160h`. `spec.monitoring.traces.sampleRatio` is unset.
- The MLflow ClusterRole is `mlflow-operator-mlflow-integration`.
- Three GPU workers, each with one NVIDIA L40S (48 GB). The default StorageClass is `gp3-csi`. `gp2-csi` is also present. There is no OpenShift Data Foundation storage class.
- cert-manager is installed.

Absent at the start:

- MCP Lifecycle Operator and the `MCPServer` custom resource.
- The agents operator, so `AgentRuntime` and `AgentCard` do not exist.
- A published MaaS model, a Guardrails Gateway URL, and Secret `flyfish-maas`.
- Memory Hub.
- An MLflow server custom resource. The operator is on; the server is not.
- OpenShell.
- Namespaces `flyfish-ai` and `flyfish-ui`.

`oc apply -k deploy/ai` stops on the missing `MCPServer` and `AgentRuntime` types until those APIs exist. SeaweedFS on `gp3-csi` is the artifact bucket for this cluster.

1. OpenShift 4.20 or newer, with OpenShift AI 3.5.
2. MCP Lifecycle Operator, and the dashboard `mcpCatalog` feature flag. FlyFish registers one `MCPServer` per tool so each server appears in the AI Hub MCP Catalog.
3. The agents operator that reconciles `AgentRuntime` and publishes `AgentCard` resources. Each FlyFish agent Deployment carries `protocol.kagenti.io/a2a: "true"`, sets `kagenti.io/inject: disabled`, and serves `/.well-known/agent-card.json`. `deploy/prerequisites/agents-crds/` holds the CRDs. The controller chart `oci://ghcr.io/kagenti/kagenti-operator/kagenti-operator-chart` is not anonymously pullable; `scripts/install-lab.sh` records that failure instead of treating the CRDs as a running controller.
4. Publish `RedHatAI/gpt-oss-20b` from the OpenShift AI 3.5 Model Catalog as MaaS (`MaaSModelRef`, `MaaSSubscription`, `MaaSAuthPolicy`). Modelcar `oci://registry.redhat.io/rhelai1/modelcar-gpt-oss-20b:1.5`. It is validated at 16 GB on one NVIDIA L4. The unquantized Phi-4-reasoning model is 34 GB and is not listed for one L4; `gpt-oss-120b` needs four L4s. Put the Guardrails Gateway URL in the `flyfish-platform` ConfigMap key `maasBaseUrl`. The ConfigMap keys `maasModel` and `ogxModel` are already `RedHatAI/gpt-oss-20b`. Create a Secret `flyfish-maas` with key `apiKey`. Agents call only that guarded OpenAI-compatible URL and send `Reasoning: high` in the system prompt. The guardrail detector is Granite Guardian on the TrustyAI FMS orchestrator (the small HAP detector). `granite-guardian-3.2-5b` is 14 GB and the validated matrix lists it for H200, not L4, so it is not the detector to place on the same L4 as the reasoning model.
5. An OGX server with a remote pgvector provider. The in-namespace database is `flyfish-pgvector`. After AutoRAG selects a pattern, set `ogxBaseUrl`, `ogxVectorStoreId`, and `autoragPatternId` in `flyfish-platform`, and create Secret `flyfish-ogx` with key `apiKey`.
6. A pipeline server in `flyfish-ai` with AutoRAG pipelines enabled (`spec.apiServer.managedPipelines: {}`), plus dashboard flags `genAiStudio` and `autorag`.
7. OpenShell gateway, the Developer Preview in OpenShift AI 3.5. `scripts/install-lab.sh` installs chart `oci://ghcr.io/nvidia/openshell/helm-chart` version `0.0.85` into namespace `openshell`. The chart runs as UID 1000, which `restricted-v2` rejects, so the `openshell` ServiceAccount needs the `nonroot` SCC: `oc adm policy add-scc-to-user nonroot -z openshell -n openshell`. Apply the policies in `deploy/openshell/` with `openshell policy set` only after replacing `maas-gateway.example.svc` and `ogx.example.svc` with the real Service hostnames. FlyFish containers themselves request `restricted-v2` compatible settings.
8. Memory Hub from https://github.com/redhat-ai-americas/memory-hub using its upstream installer (`make install`). That installer uses its own namespaces. This lab does not deploy MinIO. Point Memory Hub at the FlyFish SeaweedFS Service before `make install`:

`MEMORYHUB_S3_ENDPOINT=seaweedfs.flyfish-ai.svc.cluster.local:8333`

`MEMORYHUB_S3_BUCKET=memoryhub`

`MEMORYHUB_S3_SECURE=false`

Copy Secret `flyfish-s3` from `flyfish-ai` into `memory-hub-mcp` as `memoryhub-minio-credentials`, with `AWS_ACCESS_KEY_ID` stored as `MINIO_ROOT_USER` and `AWS_SECRET_ACCESS_KEY` stored as `MINIO_ROOT_PASSWORD`. SeaweedFS is already running and the identity can create the `memoryhub` bucket. After Memory Hub is up, create Secret `flyfish-memoryhub` in `flyfish-ai` with key `apiKey`. Confirm `memoryHubUrl` in `flyfish-platform` matches the MCP Service.
9. Agent observability, in two platform pieces. Enable tracing on `DSCInitialization` so OpenShift AI runs the OpenTelemetry collector and Tempo in `redhat-ods-monitoring`. For this demo set `spec.monitoring.traces.sampleRatio` to `"1"` so agent traces are kept. The collector address is `http://data-science-collector.redhat-ods-monitoring.svc.cluster.local:4318`. Enable MLflow with `oc patch datasciencecluster default-dsc --type=merge -p '{"spec":{"components":{"mlflowoperator":{"managementState":"Managed"}}}}'`, then apply `deploy/prerequisites/mlflow.yaml`. That manifest is a development MLflow instance (SQLite plus a PVC, with `serveArtifacts: true`). It is not part of `oc apply -k deploy/ai`. On OpenShift AI 3.5.1 the ClusterRole is `mlflow-operator-mlflow-integration`. Traces show in the MLflow UI under experiment `flyfish-agents`, workspace `flyfish-ai`, and in Tempo through `tempo-query-frontend` in `redhat-ods-monitoring`.

`scripts/install-lab.sh` applies items 2, 3 (CRDs), 6 (the pipeline server, when that CRD exists), and 9. It also attempts the agents operator chart and the OpenShell gateway, and it applies `deploy/ai` and `deploy/ui`. It does not create `flyfish-maas`, `flyfish-memoryhub`, or `flyfish-ogx`. Memory Hub remains `make install` from the upstream repository.

Do not invent API keys. If a secret is missing, stop and record it in `.agent/ISSUES.md`.
