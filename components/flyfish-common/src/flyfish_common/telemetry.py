"""OpenTelemetry traces for FlyFish agents.

Spans export two ways when the platform endpoints are set:

- OpenShift AI's collector, which stores them in Tempo
  (``OTEL_EXPORTER_OTLP_ENDPOINT``, OTLP/HTTP).
- The cluster MLflow tracking server's OTLP ingest
  (``MLFLOW_TRACKING_URI`` + ``/v1/traces``), filed under the
  ``flyfish-agents`` experiment in the ``flyfish-ai`` workspace.

Neither endpoint is required. A missing or unreachable backend is logged
and the agent still serves traffic. Trace attributes carry the agent, skill,
trip id, and model name. They do not carry the traveler prompt, citizenship,
or tool payloads.
"""

from __future__ import annotations

import json
import os
import ssl
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

EXPERIMENT_NAME = "flyfish-agents"
TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"


def traces_endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1/traces"):
        return base
    return f"{base}/v1/traces"


def mlflow_otlp_headers(token: str, experiment_id: str, workspace: str) -> dict[str, str]:
    headers = {
        "x-mlflow-experiment-id": experiment_id,
        "X-MLFLOW-WORKSPACE": workspace,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def read_token(path: str = TOKEN_PATH) -> str:
    file = Path(path)
    if not file.is_file():
        return ""
    return file.read_text().strip()


def resolve_experiment_id(base_url: str, name: str, headers: dict[str, str], opener) -> str:
    """Return the MLflow experiment id, creating the experiment when it is absent."""
    query = urlencode({"experiment_name": name})
    query_url = f"{base_url.rstrip('/')}/api/2.0/mlflow/experiments/get-by-name?{query}"
    status, payload = opener("GET", query_url, None, headers)
    if status == 200 and payload.get("experiment", {}).get("experiment_id"):
        return str(payload["experiment"]["experiment_id"])
    status, payload = opener(
        "POST",
        f"{base_url.rstrip('/')}/api/2.0/mlflow/experiments/create",
        {"name": name},
        headers,
    )
    if status == 200 and payload.get("experiment_id"):
        return str(payload["experiment_id"])
    if payload.get("error_code") == "RESOURCE_ALREADY_EXISTS":
        status, payload = opener("GET", query_url, None, headers)
        if status == 200 and payload.get("experiment", {}).get("experiment_id"):
            return str(payload["experiment"]["experiment_id"])
    raise RuntimeError(f"MLflow experiment {name} was not created (HTTP {status})")


class MLflowSpanExporter:
    """OTLP/HTTP exporter that re-reads the service-account token on each batch."""

    def __init__(self, factory, token_path: str, experiment_id: str, workspace: str) -> None:
        self._factory = factory
        self._token_path = token_path
        self._experiment_id = experiment_id
        self._workspace = workspace
        self._token = ""
        self._inner = None

    def export(self, spans):
        token = read_token(self._token_path)
        if self._inner is None or token != self._token:
            if self._inner is not None:
                self._inner.shutdown()
            self._token = token
            headers = mlflow_otlp_headers(token, self._experiment_id, self._workspace)
            self._inner = self._factory(headers)
        return self._inner.export(spans)

    def shutdown(self):
        if self._inner is not None:
            return self._inner.shutdown()
        return None

    def force_flush(self, timeout_millis: int = 30000):
        if self._inner is not None and hasattr(self._inner, "force_flush"):
            return self._inner.force_flush(timeout_millis)
        return True


def configure_tracing(service_name: str) -> None:
    """Install exporters once. Safe when the OpenTelemetry packages are absent."""
    otel = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    mlflow = os.environ.get("MLFLOW_TRACKING_URI", "").strip()
    if not otel and not mlflow:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        print("flyfish tracing: OpenTelemetry SDK is not installed", flush=True)
        return
    provider = TracerProvider(resource=Resource.create({"service.name": service_name, "service.namespace": "flyfish-ai"}))
    if otel:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=traces_endpoint(otel)),
                schedule_delay_millis=1000,
            )
        )
        print(f"flyfish tracing: otel {traces_endpoint(otel)}", flush=True)
    if mlflow:
        _add_mlflow_exporter(provider, mlflow, BatchSpanProcessor)
    try:
        trace.set_tracer_provider(provider)
    except Exception as exc:  # pragma: no cover - provider already installed in this process
        print(f"flyfish tracing: provider already set ({exc})", flush=True)


def _add_mlflow_exporter(provider, tracking_uri: str, processor_cls) -> None:
    workspace = os.environ.get("MLFLOW_WORKSPACE", "flyfish-ai").strip() or "flyfish-ai"
    name = os.environ.get("MLFLOW_EXPERIMENT", EXPERIMENT_NAME).strip() or EXPERIMENT_NAME
    token_path = os.environ.get("MLFLOW_TOKEN_PATH", TOKEN_PATH)
    ca_file = os.environ.get("MLFLOW_CA_FILE", "")
    headers = mlflow_otlp_headers(read_token(token_path), "", workspace)
    headers.pop("x-mlflow-experiment-id", None)
    try:
        experiment_id = resolve_experiment_id(tracking_uri, name, headers, _opener(ca_file))
    except Exception as exc:
        print(f"flyfish tracing: MLflow experiment lookup failed: {exc}", flush=True)
        return
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    certificate = ca_file if ca_file and Path(ca_file).is_file() else None

    def factory(otlp_headers: dict[str, str]):
        kwargs = {"endpoint": traces_endpoint(tracking_uri), "headers": otlp_headers}
        if certificate:
            kwargs["certificate_file"] = certificate
        return OTLPSpanExporter(**kwargs)

    provider.add_span_processor(
        processor_cls(
            MLflowSpanExporter(factory, token_path, experiment_id, workspace),
            schedule_delay_millis=1000,
        )
    )
    print(f"flyfish tracing: mlflow experiment {name} id {experiment_id} workspace {workspace}", flush=True)


def _opener(ca_file: str):
    context = None
    if ca_file and Path(ca_file).is_file():
        context = ssl.create_default_context(cafile=ca_file)

    def opener(method: str, url: str, payload: dict | None, headers: dict[str, str]):
        data = None if payload is None else json.dumps(payload).encode()
        request = Request(url, data=data, method=method)
        request.add_header("Accept", "application/json")
        if payload is not None:
            request.add_header("Content-Type", "application/json")
        for key, value in headers.items():
            request.add_header(key, value)
        try:
            with urlopen(request, timeout=5, context=context) as response:
                raw = response.read().decode()
                return response.status, json.loads(raw) if raw else {}
        except HTTPError as exc:
            raw = exc.read().decode() if exc.fp else ""
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                body = {"message": raw[:200]}
            return exc.code, body
        except URLError as exc:
            raise RuntimeError(str(exc.reason)) from exc

    return opener


def _otel():
    try:
        from opentelemetry import trace
        from opentelemetry.propagate import extract, inject
        from opentelemetry.trace import SpanKind, Status, StatusCode
    except ImportError:
        return None
    return trace, extract, inject, SpanKind, Status, StatusCode


@contextmanager
def server_span(name: str, carrier: dict, attributes: dict):
    loaded = _otel()
    if loaded is None:
        yield None
        return
    trace, extract, _inject, SpanKind, Status, StatusCode = loaded
    tracer = trace.get_tracer("flyfish")
    with tracer.start_as_current_span(name, context=extract(carrier or {}), kind=SpanKind.SERVER) as current:
        _set(current, attributes)
        try:
            yield current
        except Exception as exc:
            current.record_exception(exc)
            current.set_status(Status(StatusCode.ERROR))
            raise


@contextmanager
def client_span(method: str, url: str, headers: dict):
    loaded = _otel()
    if loaded is None:
        yield None
        return
    trace, _extract, inject, SpanKind, Status, StatusCode = loaded
    parsed = urlsplit(url)
    tracer = trace.get_tracer("flyfish")
    with tracer.start_as_current_span(f"HTTP {method}", kind=SpanKind.CLIENT) as current:
        _set(
            current,
            {
                "http.request.method": method,
                "server.address": parsed.hostname or "",
                "url.path": parsed.path,
            },
        )
        inject(headers)
        try:
            yield current
        except Exception as exc:
            current.record_exception(exc)
            current.set_status(Status(StatusCode.ERROR))
            raise


@contextmanager
def span(name: str, attributes: dict | None = None):
    loaded = _otel()
    if loaded is None:
        yield None
        return
    trace, _extract, _inject, _kind, Status, StatusCode = loaded
    tracer = trace.get_tracer("flyfish")
    with tracer.start_as_current_span(name) as current:
        _set(current, attributes or {})
        try:
            yield current
        except Exception as exc:
            current.record_exception(exc)
            current.set_status(Status(StatusCode.ERROR))
            raise


def _set(current, attributes: dict) -> None:
    for key, value in attributes.items():
        if value is None or value == "":
            continue
        current.set_attribute(key, value)


def mark_http_status(current, status: int) -> None:
    if current is None:
        return
    current.set_attribute("http.response.status_code", status)
    if status >= 400:
        loaded = _otel()
        if loaded is None:
            return
        _trace, _extract, _inject, _kind, Status, StatusCode = loaded
        current.set_status(Status(StatusCode.ERROR))
