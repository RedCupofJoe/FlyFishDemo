#!/usr/bin/env bash
# Apply FlyFish after the platform prerequisites exist.
# Exits without changing the cluster when oc is not logged in.
set -euo pipefail

if ! oc whoami >/dev/null 2>&1; then
  echo "oc is not logged in. Cluster deployment is blocked until credentials exist." >&2
  exit 2
fi

oc apply -k deploy/ai
oc apply -k deploy/ui

if oc get crd datasciencepipelinesapplications.opendatahub.io >/dev/null 2>&1; then
  oc apply -f deploy/prerequisites/dspa.yaml
else
  echo "DataSciencePipelinesApplication CRD is not installed. Skip the pipeline server until OpenShift AI pipelines are enabled."
fi

if oc get storageclass openshift-storage.noobaa.io >/dev/null 2>&1; then
  echo "OpenShift Data Foundation storage class is present. See deploy/ai/odf/README.md before relying on SeaweedFS."
fi

echo "Start image builds with: oc get buildconfig -n flyfish-ai -o name"
echo "Upload deploy/ai/autorag/seed-guide.md and eval.json, then create the AutoRAG run in the dashboard."
