#!/usr/bin/env python3
"""Write the OpenShift manifests for the two FlyFish namespaces."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AI = ROOT / "deploy" / "ai"
UI = ROOT / "deploy" / "ui"
SHELL = ROOT / "deploy" / "openshell"
GIT = "https://github.com/RedCupofJoe/FlyFishDemo.git"
REGISTRY = "image-registry.openshift-image-registry.svc:5000/flyfish-ai"

MCP = [
    ("weather-mcp", "weather"),
    ("travel-advisory-mcp", "travel_advisory"),
    ("crime-stats-mcp", "crime_statistics"),
    ("landmarks-mcp", "landmarks"),
    ("attractions-mcp", "attractions"),
    ("nightlife-mcp", "nightlife"),
    ("trends-mcp", "trends"),
    ("emergency-mcp", "emergency"),
    ("embassy-mcp", "embassy"),
]

MCP_URLS = {
    "weather": [("WEATHER_MCP_URL", "weather-mcp")],
    "risk": [("TRAVEL_ADVISORY_MCP_URL", "travel-advisory-mcp"), ("CRIME_STATS_MCP_URL", "crime-stats-mcp")],
    "places": [
        ("LANDMARKS_MCP_URL", "landmarks-mcp"),
        ("ATTRACTIONS_MCP_URL", "attractions-mcp"),
        ("NIGHTLIFE_MCP_URL", "nightlife-mcp"),
        ("TRENDS_MCP_URL", "trends-mcp"),
    ],
    "consular": [("EMERGENCY_MCP_URL", "emergency-mcp"), ("EMBASSY_MCP_URL", "embassy-mcp")],
}

AGENTS = [
    ("planner-agent", "planner", ["plan-trip"]),
    ("weather-agent", "weather", ["seasonal-weather"]),
    ("risk-agent", "risk", ["travel-advisory", "crime-statistics"]),
    ("places-agent", "places", ["landmarks", "attractions", "nightlife", "trends"]),
    ("consular-agent", "consular", ["emergency", "embassy"]),
    ("guide-agent", "guide", ["compose-guide"]),
    ("response-agent", "response", ["generate-report", "answer-report"]),
]

PEER = {
    "planner": ["weather-agent", "risk-agent", "places-agent", "consular-agent", "guide-agent"],
    "response": ["planner-agent"],
}


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n")


def image(name: str) -> str:
    return f"{REGISTRY}/{name}:0.1.0"


def svc(name: str, port: int = 8080) -> str:
    return f"http://{name}.flyfish-ai.svc.cluster.local:{port}"


def env_block(pairs: list[tuple[str, str]], indent: str = "            ") -> str:
    lines = []
    for key, value in pairs:
        lines.append(f"{indent}- name: {key}")
        lines.append(f"{indent}  value: {json.dumps(value)}")
    return "\n".join(lines)


def security_pod() -> str:
    return """      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault"""


def security_container() -> str:
    return """          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
            runAsNonRoot: true"""


def buildconfig(name: str, dockerfile: str, arg: str, value: str) -> str:
    return f"""apiVersion: image.openshift.io/v1
kind: ImageStream
metadata:
  name: {name}
  namespace: flyfish-ai
  labels:
    app.kubernetes.io/part-of: flyfish
---
apiVersion: build.openshift.io/v1
kind: BuildConfig
metadata:
  name: {name}
  namespace: flyfish-ai
  labels:
    app.kubernetes.io/part-of: flyfish
spec:
  source:
    type: Git
    git:
      uri: {GIT}
      ref: main
  strategy:
    type: Docker
    dockerStrategy:
      dockerfilePath: {dockerfile}
      buildArgs:
        - name: {arg}
          value: {value}
  output:
    to:
      kind: ImageStreamTag
      name: {name}:0.1.0
  triggers: []
"""


def deployment(name: str, agent: str, extra_env: list[tuple[str, str]], skills: list[str]) -> str:
    skills_json = json.dumps(skills)
    return f"""apiVersion: v1
kind: ServiceAccount
metadata:
  name: {name}
  namespace: flyfish-ai
  labels:
    app.kubernetes.io/part-of: flyfish
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
  namespace: flyfish-ai
  labels:
    app: {name}
    app.kubernetes.io/part-of: flyfish
    protocol.kagenti.io/a2a: "true"
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
        app.kubernetes.io/part-of: flyfish
        protocol.kagenti.io/a2a: "true"
      annotations:
        kagenti.io/skills: {json.dumps(skills_json)}
    spec:
{security_pod()}
      serviceAccountName: {name}
      containers:
        - name: agent
          image: {image(name)}
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 8080
{security_container()}
          env:
{env_block([("FLYFISH_AGENT", agent), ("PORT", "8080")] + extra_env)}
            - name: MAAS_BASE_URL
              valueFrom:
                configMapKeyRef:
                  name: flyfish-platform
                  key: maasBaseUrl
                  optional: true
            - name: MAAS_API_KEY
              valueFrom:
                secretKeyRef:
                  name: flyfish-maas
                  key: apiKey
                  optional: true
            - name: MAAS_MODEL
              valueFrom:
                configMapKeyRef:
                  name: flyfish-platform
                  key: maasModel
            - name: MEMORYHUB_URL
              valueFrom:
                configMapKeyRef:
                  name: flyfish-platform
                  key: memoryHubUrl
            - name: MEMORYHUB_API_KEY
              valueFrom:
                secretKeyRef:
                  name: flyfish-memoryhub
                  key: apiKey
                  optional: true
            - name: S3_ENDPOINT_URL
              value: {json.dumps(svc("seaweedfs", 8333))}
            - name: S3_BUCKET
              value: flyfish-artifacts
            - name: AWS_ACCESS_KEY_ID
              valueFrom:
                secretKeyRef:
                  name: flyfish-s3
                  key: AWS_ACCESS_KEY_ID
            - name: AWS_SECRET_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: flyfish-s3
                  key: AWS_SECRET_ACCESS_KEY
            - name: AWS_DEFAULT_REGION
              value: us-east-1
            - name: OGX_BASE_URL
              valueFrom:
                configMapKeyRef:
                  name: flyfish-platform
                  key: ogxBaseUrl
                  optional: true
            - name: OGX_API_KEY
              valueFrom:
                secretKeyRef:
                  name: flyfish-ogx
                  key: apiKey
                  optional: true
            - name: OGX_MODEL
              valueFrom:
                configMapKeyRef:
                  name: flyfish-platform
                  key: ogxModel
            - name: OGX_VECTOR_STORE_ID
              valueFrom:
                configMapKeyRef:
                  name: flyfish-platform
                  key: ogxVectorStoreId
                  optional: true
            - name: AUTORAG_PATTERN_ID
              valueFrom:
                configMapKeyRef:
                  name: flyfish-platform
                  key: autoragPatternId
                  optional: true
            - name: OTEL_SERVICE_NAME
              value: {name}
            - name: OTEL_EXPORTER_OTLP_PROTOCOL
              value: http/protobuf
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              valueFrom:
                configMapKeyRef:
                  name: flyfish-platform
                  key: otelExporterOtlpEndpoint
                  optional: true
            - name: MLFLOW_TRACKING_URI
              valueFrom:
                configMapKeyRef:
                  name: flyfish-platform
                  key: mlflowTrackingUri
                  optional: true
            - name: MLFLOW_EXPERIMENT
              valueFrom:
                configMapKeyRef:
                  name: flyfish-platform
                  key: mlflowExperiment
                  optional: true
            - name: MLFLOW_WORKSPACE
              valueFrom:
                configMapKeyRef:
                  name: flyfish-platform
                  key: mlflowWorkspace
                  optional: true
            - name: MLFLOW_CA_FILE
              value: /etc/ssl/service-ca/service-ca.crt
          volumeMounts:
            - name: service-ca
              mountPath: /etc/ssl/service-ca
              readOnly: true
          readinessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 3
            periodSeconds: 10
          resources:
            requests:
              cpu: 100m
              memory: 384Mi
            limits:
              cpu: "1"
              memory: 768Mi
      volumes:
        - name: service-ca
          configMap:
            name: openshift-service-ca.crt
            optional: true
---
apiVersion: v1
kind: Service
metadata:
  name: {name}
  namespace: flyfish-ai
  labels:
    app: {name}
    app.kubernetes.io/part-of: flyfish
spec:
  selector:
    app: {name}
  ports:
    - name: http
      port: 8080
      targetPort: http
---
apiVersion: agent.kagenti.dev/v1alpha1
kind: AgentRuntime
metadata:
  name: {name}
  namespace: flyfish-ai
  labels:
    app.kubernetes.io/part-of: flyfish
spec:
  type: agent
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {name}
"""


def mcpserver(name: str, tool: str) -> str:
    built = buildconfig(name, "components/mcp/Containerfile", "FLYFISH_TOOL", tool)
    return built + f"""---
apiVersion: mcp.x-k8s.io/v1alpha1
kind: MCPServer
metadata:
  name: {name}
  namespace: flyfish-ai
  labels:
    app.kubernetes.io/part-of: flyfish
    flyfish/tool: {tool}
spec:
  source:
    type: ContainerImage
    containerImage:
      ref: {image(name)}
  config:
    port: 8080
    path: /mcp
"""


def agent_env(agent: str) -> list[tuple[str, str]]:
    pairs = [(key, svc(service)) for key, service in MCP_URLS.get(agent, [])]
    for peer in PEER.get(agent, []):
        env_name = peer.replace("-agent", "").upper() + "_AGENT_URL"
        if agent == "response" and peer == "planner-agent":
            env_name = "PLANNER_AGENT_URL"
        pairs.append((env_name, svc(peer)))
    return pairs


def policy(agent_name: str, agent: str) -> str:
    hosts = [
        "memory-hub-mcp.memory-hub-mcp.svc",
        "seaweedfs.flyfish-ai.svc",
        "maas-gateway.example.svc",
        "data-science-collector.redhat-ods-monitoring.svc",
        "mlflow.redhat-ods-applications.svc",
    ]
    ports = {
        "memory-hub-mcp.memory-hub-mcp.svc": 8080,
        "seaweedfs.flyfish-ai.svc": 8333,
        "maas-gateway.example.svc": 443,
        "data-science-collector.redhat-ods-monitoring.svc": 4318,
        "mlflow.redhat-ods-applications.svc": 8443,
    }
    for _key, service in MCP_URLS.get(agent, []):
        host = f"{service}.flyfish-ai.svc"
        hosts.append(host)
        ports[host] = 8080
    for peer in PEER.get(agent, []):
        host = f"{peer}.flyfish-ai.svc"
        hosts.append(host)
        ports[host] = 8080
    if agent == "response":
        hosts.append("ogx.example.svc")
        ports["ogx.example.svc"] = 443
    blocks = []
    for host in hosts:
        key = host.split(".")[0].replace("-", "_")
        blocks.append(
            f"""  {key}:
    name: {key}
    endpoints:
      - host: {host}
        port: {ports[host]}
    binaries:
      - path: /opt/app-root/bin/python3
      - path: /usr/bin/python3
      - path: /usr/bin/python3.12"""
        )
    body = "\n".join(blocks)
    return f"""# OpenShell sandbox policy for {agent_name}.
# Replace maas-gateway.example.svc and ogx.example.svc with the cluster Service hostnames.
# Endpoints without a protocol allow the TCP stream, which matches in-cluster HTTP.
version: 1
filesystem_policy:
  include_workdir: true
  read_only:
    - /usr
    - /lib
    - /proc
    - /dev/urandom
    - /opt
    - /etc
    - /var/log
  read_write:
    - /sandbox
    - /tmp
    - /data
    - /dev/null
landlock:
  compatibility: best_effort
network_policies:
{body}
"""


def platform() -> str:
    return """apiVersion: v1
kind: ConfigMap
metadata:
  name: flyfish-platform
  namespace: flyfish-ai
  labels:
    app.kubernetes.io/part-of: flyfish
data:
  maasBaseUrl: ""
  maasModel: RedHatAI/gpt-oss-20b
  memoryHubUrl: http://memory-hub-mcp.memory-hub-mcp.svc.cluster.local:8080
  ogxBaseUrl: ""
  ogxModel: RedHatAI/gpt-oss-20b
  ogxVectorStoreId: ""
  autoragPatternId: ""
  otelExporterOtlpEndpoint: http://data-science-collector.redhat-ods-monitoring.svc.cluster.local:4318
  mlflowTrackingUri: https://mlflow.redhat-ods-applications.svc.cluster.local:8443
  mlflowExperiment: flyfish-agents
  mlflowWorkspace: flyfish-ai
"""


def storage() -> str:
    return """apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: flyfish-pgvector
  namespace: flyfish-ai
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: flyfish-pg-init
  namespace: flyfish-ai
data:
  init.sql: |
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE TABLE IF NOT EXISTS flyfish_artifact_index (
      id TEXT PRIMARY KEY,
      trip_id TEXT NOT NULL,
      source_key TEXT NOT NULL,
      heading TEXT NOT NULL,
      content TEXT NOT NULL,
      autorag_pattern TEXT,
      indexed_at TIMESTAMPTZ DEFAULT NOW()
    );
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flyfish-pgvector
  namespace: flyfish-ai
  labels:
    app: flyfish-pgvector
    app.kubernetes.io/part-of: flyfish
spec:
  replicas: 1
  selector:
    matchLabels:
      app: flyfish-pgvector
  template:
    metadata:
      labels:
        app: flyfish-pgvector
        app.kubernetes.io/part-of: flyfish
    spec:
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: postgres
          image: pgvector/pgvector:pg16
          env:
            - name: POSTGRES_USER
              valueFrom:
                secretKeyRef:
                  name: flyfish-pg
                  key: POSTGRES_USER
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: flyfish-pg
                  key: POSTGRES_PASSWORD
            - name: POSTGRES_DB
              valueFrom:
                secretKeyRef:
                  name: flyfish-pg
                  key: POSTGRES_DB
            - name: PGDATA
              value: /var/lib/postgresql/data/pgdata
          ports:
            - name: postgres
              containerPort: 5432
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
            runAsNonRoot: true
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
            - name: init
              mountPath: /docker-entrypoint-initdb.d
          readinessProbe:
            tcpSocket:
              port: postgres
            initialDelaySeconds: 5
            periodSeconds: 10
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: "1"
              memory: 1Gi
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: flyfish-pgvector
        - name: init
          configMap:
            name: flyfish-pg-init
---
apiVersion: v1
kind: Service
metadata:
  name: flyfish-pgvector
  namespace: flyfish-ai
spec:
  selector:
    app: flyfish-pgvector
  ports:
    - name: postgres
      port: 5432
      targetPort: postgres
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: seaweed-s3
  namespace: flyfish-ai
data:
  s3.json: |
    {
      "identities": [
        {
          "name": "flyfish",
          "credentials": [
            {"accessKey": "flyfish-demo", "secretKey": "flyfish-demo-secret"}
          ],
          "actions": ["Admin", "Read", "Write", "List", "Tagging"]
        }
      ]
    }
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: seaweedfs
  namespace: flyfish-ai
  labels:
    app: seaweedfs
    app.kubernetes.io/part-of: flyfish
spec:
  replicas: 1
  selector:
    matchLabels:
      app: seaweedfs
  template:
    metadata:
      labels:
        app: seaweedfs
        app.kubernetes.io/part-of: flyfish
    spec:
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: seaweedfs
          image: docker.io/chrislusf/seaweedfs:3.80
          command: ["weed"]
          args:
            - server
            - -dir=/data
            - -ip.bind=0.0.0.0
            - -master.port=9333
            - -volume.port=8081
            - -filer=false
            - -s3
            - -s3.port=8333
            - -s3.config=/etc/seaweed/s3.json
          ports:
            - name: s3
              containerPort: 8333
            - name: master
              containerPort: 9333
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
            runAsNonRoot: true
          volumeMounts:
            - name: data
              mountPath: /data
            - name: config
              mountPath: /etc/seaweed
          readinessProbe:
            tcpSocket:
              port: s3
            initialDelaySeconds: 5
            periodSeconds: 10
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: "1"
              memory: 512Mi
      volumes:
        - name: data
          emptyDir: {}
        - name: config
          configMap:
            name: seaweed-s3
---
apiVersion: v1
kind: Service
metadata:
  name: seaweedfs
  namespace: flyfish-ai
spec:
  selector:
    app: seaweedfs
  ports:
    - name: s3
      port: 8333
      targetPort: s3
    - name: master
      port: 9333
      targetPort: master
---
apiVersion: batch/v1
kind: Job
metadata:
  name: flyfish-create-bucket
  namespace: flyfish-ai
  labels:
    app.kubernetes.io/part-of: flyfish
spec:
  backoffLimit: 6
  template:
    spec:
      restartPolicy: OnFailure
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: create-bucket
          image: image-registry.openshift-image-registry.svc:5000/flyfish-ai/response-agent:0.1.0
          command: ["python3", "-m", "flyfish_indexer.bucket"]
          env:
            - name: S3_ENDPOINT_URL
              value: http://seaweedfs.flyfish-ai.svc.cluster.local:8333
            - name: S3_BUCKET
              value: flyfish-artifacts
            - name: AWS_ACCESS_KEY_ID
              valueFrom:
                secretKeyRef:
                  name: flyfish-s3
                  key: AWS_ACCESS_KEY_ID
            - name: AWS_SECRET_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: flyfish-s3
                  key: AWS_SECRET_ACCESS_KEY
            - name: AWS_DEFAULT_REGION
              value: us-east-1
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
            runAsNonRoot: true
"""


def indexer() -> str:
    return f"""apiVersion: batch/v1
kind: CronJob
metadata:
  name: flyfish-index
  namespace: flyfish-ai
  labels:
    app.kubernetes.io/part-of: flyfish
spec:
  suspend: true
  schedule: "0 0 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: Never
          securityContext:
            runAsNonRoot: true
            seccompProfile:
              type: RuntimeDefault
          containers:
            - name: index
              image: {image("response-agent")}
              command: ["python3", "-m", "flyfish_indexer"]
              env:
                - name: TRIP_ID
                  value: replace-with-trip-id
                - name: S3_ENDPOINT_URL
                  value: {json.dumps(svc("seaweedfs", 8333))}
                - name: S3_BUCKET
                  value: flyfish-artifacts
                - name: AWS_ACCESS_KEY_ID
                  valueFrom:
                    secretKeyRef:
                      name: flyfish-s3
                      key: AWS_ACCESS_KEY_ID
                - name: AWS_SECRET_ACCESS_KEY
                  valueFrom:
                    secretKeyRef:
                      name: flyfish-s3
                      key: AWS_SECRET_ACCESS_KEY
                - name: AUTORAG_PATTERN_ID
                  valueFrom:
                    configMapKeyRef:
                      name: flyfish-platform
                      key: autoragPatternId
                      optional: true
              securityContext:
                allowPrivilegeEscalation: false
                capabilities:
                  drop: ["ALL"]
                runAsNonRoot: true
"""


def network() -> str:
    return """apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: response-agent-from-ui
  namespace: flyfish-ai
spec:
  podSelector:
    matchLabels:
      app: response-agent
  policyTypes: [Ingress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: flyfish-ui
      ports:
        - protocol: TCP
          port: 8080
    - from:
        - podSelector: {}
      ports:
        - protocol: TCP
          port: 8080
"""


def ui() -> None:
    write(
        UI / "namespace.yaml",
        """apiVersion: v1
kind: Namespace
metadata:
  name: flyfish-ui
  labels:
    kubernetes.io/metadata.name: flyfish-ui
    app.kubernetes.io/part-of: flyfish
""",
    )
    write(
        UI / "ui.yaml",
        f"""apiVersion: image.openshift.io/v1
kind: ImageStream
metadata:
  name: flyfish-ui
  namespace: flyfish-ui
---
apiVersion: build.openshift.io/v1
kind: BuildConfig
metadata:
  name: flyfish-ui
  namespace: flyfish-ui
spec:
  source:
    type: Git
    git:
      uri: {GIT}
      ref: main
  strategy:
    type: Docker
    dockerStrategy:
      dockerfilePath: components/ui/Containerfile
  output:
    to:
      kind: ImageStreamTag
      name: flyfish-ui:0.1.0
  triggers: []
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flyfish-ui
  namespace: flyfish-ui
  labels:
    app: flyfish-ui
spec:
  replicas: 1
  selector:
    matchLabels:
      app: flyfish-ui
  template:
    metadata:
      labels:
        app: flyfish-ui
        app.kubernetes.io/part-of: flyfish
    spec:
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: httpd
          image: image-registry.openshift-image-registry.svc:5000/flyfish-ui/flyfish-ui:0.1.0
          ports:
            - name: http
              containerPort: 8080
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
            runAsNonRoot: true
          readinessProbe:
            httpGet:
              path: /
              port: http
          resources:
            requests:
              cpu: 50m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
---
apiVersion: v1
kind: Service
metadata:
  name: flyfish-ui
  namespace: flyfish-ui
spec:
  selector:
    app: flyfish-ui
  ports:
    - name: http
      port: 8080
      targetPort: http
---
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: flyfish
  namespace: flyfish-ui
spec:
  to:
    kind: Service
    name: flyfish-ui
  port:
    targetPort: http
  tls:
    termination: edge
    insecureEdgeTerminationPolicy: Redirect
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ui-egress-to-response-agent
  namespace: flyfish-ui
spec:
  podSelector:
    matchLabels:
      app: flyfish-ui
  policyTypes: [Egress]
  egress:
    - ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: flyfish-ai
          podSelector:
            matchLabels:
              app: response-agent
      ports:
        - protocol: TCP
          port: 8080
""",
    )
    write(
        UI / "kustomization.yaml",
        """apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: flyfish-ui
resources:
  - namespace.yaml
  - ui.yaml
""",
    )


def observability() -> str:
    bindings = []
    for name, _agent, _skills in AGENTS:
        bindings.append(
            f"""apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: {name}-mlflow
  namespace: flyfish-ai
  labels:
    app.kubernetes.io/part-of: flyfish
subjects:
  - kind: ServiceAccount
    name: {name}
    namespace: flyfish-ai
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: mlflow-integration
"""
        )
    return "---\n".join(bindings)


def main() -> None:
    write(
        AI / "namespace.yaml",
        """apiVersion: v1
kind: Namespace
metadata:
  name: flyfish-ai
  labels:
    kubernetes.io/metadata.name: flyfish-ai
    app.kubernetes.io/part-of: flyfish
""",
    )
    write(AI / "platform.yaml", platform())
    write(AI / "storage.yaml", storage())
    write(AI / "indexer.yaml", indexer())
    write(AI / "networkpolicy.yaml", network())
    write(AI / "observability.yaml", observability())
    resources = [
        "namespace.yaml",
        "platform.yaml",
        "storage.yaml",
        "indexer.yaml",
        "networkpolicy.yaml",
        "observability.yaml",
    ]
    for name, tool in MCP:
        filename = f"mcp-{name}.yaml"
        write(AI / filename, mcpserver(name, tool))
        resources.append(filename)
    for name, agent, skills in AGENTS:
        filename = f"agent-{name}.yaml"
        write(AI / filename, buildconfig(name, "components/agents/Containerfile", "FLYFISH_AGENT", agent) + "---\n" + deployment(name, agent, agent_env(agent), skills))
        write(SHELL / f"{name}.yaml", policy(name, agent))
        resources.append(filename)
    resource_lines = "\n".join(f"  - {item}" for item in resources)
    write(
        AI / "kustomization.yaml",
        f"""apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: flyfish-ai
resources:
{resource_lines}
generatorOptions:
  disableNameSuffixHash: true
secretGenerator:
  - name: flyfish-s3
    literals:
      - AWS_ACCESS_KEY_ID=flyfish-demo
      - AWS_SECRET_ACCESS_KEY=flyfish-demo-secret
  - name: flyfish-pg
    literals:
      - POSTGRES_USER=flyfish
      - POSTGRES_PASSWORD=flyfish-demo
      - POSTGRES_DB=flyfish
""",
    )
    ui()
    print(f"wrote {len(resources)} ai resources")


if __name__ == "__main__":
    main()
