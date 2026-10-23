"""Thin boto3 wrapper. Internal endpoint for reads/writes, public endpoint for presigned links."""
from functools import lru_cache

import boto3
from botocore.config import Config

from .config import Settings, get_settings


def _client(endpoint: str, s: Settings):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name=s.s3_region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                      retries={"max_attempts": 3}, connect_timeout=5, read_timeout=60),
    )


class Storage:
    def __init__(self, s: Settings | None = None):
        self.s = s or get_settings()
        self.bucket = self.s.s3_bucket
        self.client = _client(self.s.s3_endpoint, self.s)
        self.public = _client(self.s.s3_public_endpoint, self.s)

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)

    def bucket_ok(self) -> bool:
        self.client.head_bucket(Bucket=self.bucket)
        return True

    def put_file(self, key: str, path: str, content_type: str = "application/octet-stream") -> None:
        self.client.upload_file(path, self.bucket, key, ExtraArgs={"ContentType": content_type})

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get_file(self, key: str, path: str) -> None:
        self.client.download_file(self.bucket, key, path)

    def get_bytes(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def copy(self, src_key: str, dst_key: str) -> None:
        self.client.copy_object(Bucket=self.bucket, Key=dst_key, CopySource={"Bucket": self.bucket, "Key": src_key})

    def list_keys(self, prefix: str) -> list[str]:
        out, token = [], None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": prefix}
            if token:
                kw["ContinuationToken"] = token
            r = self.client.list_objects_v2(**kw)
            out += [o["Key"] for o in r.get("Contents", [])]
            if not r.get("IsTruncated"):
                return out
            token = r["NextContinuationToken"]

    def presign(self, key: str) -> str:
        return self.public.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=self.s.presign_ttl_s)


@lru_cache
def get_storage() -> Storage:
    return Storage()
