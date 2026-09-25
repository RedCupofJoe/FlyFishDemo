# Licenses

FlyFish application code is Apache-2.0. See the repository `LICENSE`.

Direct choices:

- PatternFly (`@patternfly/react-core`, `@patternfly/react-icons`): Apache-2.0
- React and React DOM: MIT
- Vite, Vitest, Testing Library, TypeScript: MIT
- pytest: MIT
- boto3, used by the agent image for the S3 bucket: Apache-2.0
- OpenTelemetry API, SDK, and OTLP HTTP exporter, used by the agents for traces: Apache-2.0
- Natural Earth country geometry used to build the map: public domain
- Memory Hub: Apache-2.0
- NVIDIA OpenShell: Apache-2.0

The Python services use the standard library for HTTP and MCP. The UI dependency tree includes packages PatternFly and the test runner require. `npm` and `pip` metadata are the source for those transitive licenses.

Not added by FlyFish:

- MinIO. Memory Hub's upstream installer may deploy it. MinIO's server license is AGPL. That install was chosen so Memory Hub stays on its upstream namespaces. FlyFish artifact storage is SeaweedFS (Apache-2.0) or an OpenShift Data Foundation bucket.
- Leaflet and other BSD map libraries. The map is a generated SVG.

Platform components (UBI images, MaaS, OGX, TrustyAI, OpenShift) are Red Hat entitlements and are not vendored here.
