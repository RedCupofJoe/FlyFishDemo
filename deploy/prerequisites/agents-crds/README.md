# AgentRuntime CRDs

These CustomResourceDefinitions come from the Kagenti agents operator chart in [opendatahub-io/agents-operator](https://github.com/opendatahub-io/agents-operator) (`charts/kagenti-operator/crds`). They let `oc apply -k deploy/ai` store `AgentRuntime` objects.

The operator controller image and OCI chart (`oci://ghcr.io/kagenti/kagenti-operator/kagenti-operator-chart`) are not anonymously pullable. Until that controller is installed, `AgentRuntime` resources are stored and are not reconciled into `AgentCard` objects. FlyFish agent Deployments still serve HTTP without the controller.

Install the controller when a GitHub token with `read:packages` is available:

```bash
helm registry login ghcr.io
helm install kagenti-operator \
  oci://ghcr.io/kagenti/kagenti-operator/kagenti-operator-chart \
  --version 0.4.0-rc.2 \
  --namespace kagenti-system \
  --create-namespace
```

FlyFish pod templates set `kagenti.io/inject: disabled`. The mutating webhook only selects pods labeled `kagenti.io/type` in namespaces labeled `kagenti-enabled=true`, and it skips `kagenti.io/inject: disabled`.
