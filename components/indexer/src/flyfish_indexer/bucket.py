"""Create the artifact bucket on the in-cluster S3 service."""

from __future__ import annotations

import os

import boto3
from botocore.exceptions import ClientError


def main() -> None:
    client = boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT_URL"])
    bucket = os.environ["S3_BUCKET"]
    try:
        client.create_bucket(Bucket=bucket)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            raise
    print(f"bucket {bucket}", flush=True)


if __name__ == "__main__":
    main()
