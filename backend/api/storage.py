from __future__ import annotations

import os
from dataclasses import dataclass

from minio import Minio


@dataclass(frozen=True)
class MinioConfig:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool


def get_minio_config() -> MinioConfig:
    endpoint = os.environ.get("MINIO_ENDPOINT", "http://minio:9000")
    secure = endpoint.startswith("https://")
    endpoint = endpoint.replace("http://", "").replace("https://", "")
    access_key = os.environ.get("MINIO_ROOT_USER", "minioadmin")
    secret_key = os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin")
    bucket = os.environ.get("MINIO_BUCKET", "nodex")
    return MinioConfig(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        bucket=bucket,
        secure=secure,
    )


def get_minio_client() -> Minio:
    cfg = get_minio_config()
    return Minio(
        cfg.endpoint,
        access_key=cfg.access_key,
        secret_key=cfg.secret_key,
        secure=cfg.secure,
    )


def ensure_bucket() -> None:
    cfg = get_minio_config()
    client = get_minio_client()
    if not client.bucket_exists(cfg.bucket):
        client.make_bucket(cfg.bucket)

