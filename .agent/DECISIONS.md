# Decisions

## Namespaces

FlyFish application workloads use two namespaces: `flyfish-ai` and `flyfish-ui`. Memory Hub is installed with its upstream multi-namespace layout (`memoryhub-db`, `memory-hub-mcp`, `memoryhub-auth`, `embedding-model`, `reranker-model`, `memoryhub-ui`). FlyFish does not fork Memory Hub and does not collapse those namespaces.

MaaS, OGX, TrustyAI, the OpenTelemetry collector, Tempo, MLflow, the MCP Lifecycle Operator, the agents operator, and the OpenShell gateway stay in their platform namespaces.

## Memory kinds

Memory Hub has scopes, not kinds named personal, episodic, and semantic. FlyFish stores the kind in write metadata:

- personal → user scope, weight 0.9 (origin and citizenship)
- episodic → project scope, weight 0.8 (this trip)
- semantic → project scope, weight 0.7 (country facts reused later)

The project id is `flyfish`. The mapping is in `.memoryhub.yaml`.

## Artifact storage

FlyFish does not deploy MinIO. The default bucket is SeaweedFS in `flyfish-ai` (`docker.io/chrislusf/seaweedfs:3.80`, S3 port 8333). The demo identity `flyfish-demo` / `flyfish-demo-secret` matches ConfigMap `seaweed-s3`. An OpenShift Data Foundation `ObjectBucketClaim` is available at `deploy/ai/odf/objectbucketclaim.yaml` and is not part of the default kustomize build.

Upstream Memory Hub may still deploy its own MinIO. That AGPL server is an accepted exception because the upstream installer was chosen. It is not a FlyFish dependency.

## Reasoning and guardrails

The reasoning model is `RedHatAI/gpt-oss-20b` (modelcar `oci://registry.redhat.io/rhelai1/modelcar-gpt-oss-20b:1.5`). It is the strongest reasoning model in the OpenShift AI 3.5 catalog that Red Hat validates on one NVIDIA L4 (16 GB). Agents call it only through the Guardrails Gateway. Granite Guardian on the TrustyAI FMS orchestrator is the safety detector. `granite-guardian-3.2-5b` is not placed on the same L4; the validated matrix lists that model for H200.

`Phi-4-reasoning` in BF16 is 34 GB and is not listed for one L4. `gpt-oss-120b` needs four L4s.

## Observability

Agents export OpenTelemetry traces to the OpenShift AI collector (Tempo) and to MLflow OTLP ingest. The experiment name is `flyfish-agents` and the workspace is `flyfish-ai`. Agent ServiceAccounts are bound to ClusterRole `mlflow-integration`. Span attributes omit the traveler prompt and tool payloads.

## Licenses

Application code is Apache-2.0. Direct dependencies are Apache-2.0 or MIT. The map is generated from public-domain Natural Earth geometry. See `docs/licenses.md`.
