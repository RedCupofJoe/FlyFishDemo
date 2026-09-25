"""Artifact storage. Files for local runs, S3 for the cluster bucket."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol


class ArtifactStore(Protocol):
    def put_text(self, key: str, body: str, content_type: str = "text/markdown") -> str: ...

    def get_text(self, key: str) -> str: ...

    def list_keys(self, prefix: str) -> list[str]: ...


class FileArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def put_text(self, key: str, body: str, content_type: str = "text/markdown") -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        return key

    def get_text(self, key: str) -> str:
        return self._path(key).read_text()

    def list_keys(self, prefix: str) -> list[str]:
        base = self._path(prefix)
        if base.is_file():
            return [prefix]
        if not base.exists():
            parent = base.parent
            if not parent.exists():
                return []
            return sorted(
                str(path.relative_to(self.root))
                for path in parent.rglob("*")
                if path.is_file() and str(path.relative_to(self.root)).startswith(prefix)
            )
        return sorted(
            str(path.relative_to(self.root)) for path in base.rglob("*") if path.is_file()
        )

    def _path(self, key: str) -> Path:
        relative = Path(key)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Refusing artifact key {key}")
        return self.root / relative


class S3ArtifactStore:
    def __init__(self, bucket: str, client) -> None:
        self.bucket = bucket
        self.client = client

    def put_text(self, key: str, body: str, content_type: str = "text/markdown") -> str:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body.encode(),
            ContentType=content_type,
        )
        return key

    def get_text(self, key: str) -> str:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read().decode()

    def list_keys(self, prefix: str) -> list[str]:
        response = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        return [item["Key"] for item in response.get("Contents", [])]


def store_from_env(default_root: Path) -> ArtifactStore:
    bucket = os.environ.get("S3_BUCKET", "")
    if not bucket:
        root = Path(os.environ.get("ARTIFACT_DIR", str(default_root)))
        return FileArtifactStore(root)
    import boto3

    client = boto3.client("s3", endpoint_url=os.environ.get("S3_ENDPOINT_URL") or None)
    return S3ArtifactStore(bucket, client)
