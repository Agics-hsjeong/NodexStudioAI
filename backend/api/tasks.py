from __future__ import annotations

from celery import shared_task
from django.db import transaction

from .embeddings import embed_8
from .models import Chunk, FileObject
from .storage import ensure_bucket, get_minio_client, get_minio_config


def _chunk_text(text: str, max_chars: int = 800) -> list[str]:
    parts = []
    buf = ""
    for para in text.splitlines():
        if not para.strip():
            continue
        if len(buf) + len(para) + 1 <= max_chars:
            buf = (buf + "\n" + para).strip()
        else:
            if buf:
                parts.append(buf)
            buf = para.strip()
    if buf:
        parts.append(buf)
    return parts[:50]  # MVP 안전 상한


@shared_task(bind=True, max_retries=5, default_retry_delay=5)
def ingest_fileobject(self, file_id: int) -> None:
    try:
        print("[ingest] start", file_id, flush=True)
        f = FileObject.objects.select_related("project").get(id=int(file_id))
        ensure_bucket()
        cfg = get_minio_config()
        client = get_minio_client()
        obj = client.get_object(cfg.bucket, f.object_key)
        try:
            content = obj.read().decode("utf-8", errors="replace")
        finally:
            obj.close()
            obj.release_conn()

        chunks = _chunk_text(content)
        with transaction.atomic():
            Chunk.objects.filter(file_id=f.id).delete()
            for i, c in enumerate(chunks):
                Chunk.objects.create(
                    project_id=f.project_id,
                    file_id=f.id,
                    chunk_index=i,
                    content=c,
                    embedding=embed_8(c),
                )
            FileObject.objects.filter(id=f.id).update(
                index_status=FileObject.IndexStatus.READY,
                last_error="",
            )
        print("[ingest] done", file_id, "chunks", len(chunks), flush=True)
    except Exception as e:
        FileObject.objects.filter(id=int(file_id)).update(
            index_status=FileObject.IndexStatus.FAILED,
            last_error=str(e)[:500],
        )
        print("[ingest] failed", file_id, str(e), flush=True)
        raise

