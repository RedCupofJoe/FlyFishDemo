"""Small JSON HTTP client used by MCP tools."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flyfish_common.telemetry import client_span


class HttpError(RuntimeError):
    pass


class UrllibClient:
    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def get_json(self, url: str, headers: dict | None = None, params: dict | None = None):
        if params:
            url = f"{url}?{urlencode(params)}"
        return self._read("GET", url, headers=headers)

    def post_json(self, url: str, payload: dict, headers: dict | None = None):
        body = json.dumps(payload).encode()
        merged = {"Content-Type": "application/json", **(headers or {})}
        return self._read("POST", url, data=body, headers=merged)

    def _read(self, method: str, url: str, data: bytes | None = None, headers: dict | None = None):
        merged = dict(headers or {})
        with client_span(method, url, merged) as span:
            request = Request(url, data=data, method=method)
            request.add_header("User-Agent", "FlyFishDemo/0.1 (+https://github.com/RedCupofJoe/FlyFishDemo)")
            request.add_header("Accept", "application/json")
            for key, value in merged.items():
                request.add_header(key, value)
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    if span is not None:
                        span.set_attribute("http.response.status_code", getattr(response, "status", 200))
                    raw = response.read().decode()
            except HTTPError as exc:
                if span is not None:
                    span.set_attribute("http.response.status_code", exc.code)
                raise HttpError(f"{method} {url} returned {exc.code}") from exc
            except URLError as exc:
                raise HttpError(f"{method} {url} failed: {exc.reason}") from exc
        if not raw:
            return {}
        return json.loads(raw)
