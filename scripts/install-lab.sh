#!/usr/bin/env bash
# Install the platform pieces FlyFish needs on OpenShift AI 3.5.
# Does not create API-key Secrets. Exits 2 when oc is not logged in.
# Exits 1 when a required piece could not be installed. Messages name what is still missing.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! oc whoami >/dev/null 2>&1; then
  echo "oc is not logged in. Cluster deployment is blocked until credentials exist." >&2
  exit 2
fi

failed=0
note() { printf '%s\n' "$*"; }
fail() { printf 'FAILED: %s\n' "$*" >&2; failed=1; }

note "Enable the MCP Lifecycle Operator"
oc patch datasciencecluster default-dsc --type=merge \
  -p '{"spec":{"components":{"mcplifecycleoperator":{"managementState":"Managed"}}}}' \
  || fail "could not enable mcplifecycleoperator on DataScienceCluster default-dsc"

note "Show MCP servers in the dashboard catalog"
oc patch odhdashboardconfig odh-dashboard-config -n redhat-ods-applications --type=merge \
  -p '{"spec":{"dashboardConfig":{"mcpCatalog":true}}}' \
  || fail "could not set dashboardConfig.mcpCatalog"

note "Apply the development MLflow server"
oc apply -f deploy/prerequisites/mlflow.yaml \
  || fail "could not apply deploy/prerequisites/mlflow.yaml"

note "Keep agent traces (sampleRatio 1)"
oc patch dscinitialization default-dsci --type=merge \
  -p '{"spec":{"monitoring":{"traces":{"sampleRatio":"1"}}}}' \
  || fail "could not set monitoring.traces.sampleRatio"

note "Install AgentRuntime, AgentCard, and AuthorizationPolicy CRDs"
oc apply -f deploy/prerequisites/agents-crds/ \
  || fail "could not apply deploy/prerequisites/agents-crds"

if ! oc get deploy -n kagenti-system -o name 2>/dev/null | grep -q .; then
  note "Install the Kagenti agents operator"
  if helm install kagenti-operator \
    oci://ghcr.io/kagenti/kagenti-operator/kagenti-operator-chart \
    --version 0.4.0-rc.2 \
    --namespace kagenti-system \
    --create-namespace; then
    note "Kagenti operator installed"
  else
    fail "Kagenti operator chart is not anonymously pullable from ghcr.io. CRDs are applied. The controller is not installed. Log in to ghcr.io with a token that has read:packages, then rerun this script."
  fi
else
  note "kagenti-system already has a Deployment"
fi

if oc get ns memory-hub-mcp >/dev/null 2>&1; then
  note "Memory Hub namespace memory-hub-mcp is present"
else
  fail "Memory Hub is not installed. Clone https://github.com/redhat-ai-americas/memory-hub and run make install. Then create Secret flyfish-memoryhub from the key the installer writes to ~/.config/memoryhub/api-key."
fi

if oc get ns openshell >/dev/null 2>&1; then
  note "OpenShell namespace is present"
  oc adm policy add-scc-to-user nonroot -z openshell -n openshell \
    || fail "could not grant the nonroot SCC to ServiceAccount openshell"
else
  note "Install the OpenShell gateway"
  if helm install openshell oci://ghcr.io/nvidia/openshell/helm-chart \
    --version 0.0.85 \
    --namespace openshell \
    --create-namespace; then
    note "OpenShell installed. The chart runs as UID 1000, so grant the nonroot SCC, then replace example hosts in deploy/openshell before openshell policy set."
    oc adm policy add-scc-to-user nonroot -z openshell -n openshell \
      || fail "could not grant the nonroot SCC to ServiceAccount openshell"
  else
    fail "OpenShell helm install failed. The gateway is not installed."
  fi
fi

note "Apply FlyFish namespaces"
oc apply -k deploy/ai || fail "oc apply -k deploy/ai failed"
oc apply -k deploy/ui || fail "oc apply -k deploy/ui failed"

if oc get crd datasciencepipelinesapplications.datasciencepipelinesapplications.opendatahub.io >/dev/null 2>&1; then
  note "Apply the pipeline server"
  oc apply -f deploy/prerequisites/dspa.yaml || fail "could not apply deploy/prerequisites/dspa.yaml"
else
  fail "DataSciencePipelinesApplication CRD is missing"
fi

if [[ "$failed" -ne 0 ]]; then
  echo "Lab install is PARTIAL. The messages above name what is still missing. Do not invent API keys." >&2
  exit 1
fi

echo "Lab platform pieces are installed. Create flyfish-maas, flyfish-memoryhub, and flyfish-ogx only from real keys, then start the BuildConfigs."
