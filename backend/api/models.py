from __future__ import annotations

import hashlib

from django.conf import settings
from django.db import models
from pgvector.django import VectorField


class Project(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)


class FileObject(models.Model):
    class Kind(models.TextChoices):
        SETTINGS = "settings", "settings"
        MANUSCRIPT = "manuscript", "manuscript"

    class IndexStatus(models.TextChoices):
        PENDING = "pending", "pending"
        READY = "ready", "ready"
        FAILED = "failed", "failed"

    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SETTINGS)
    relative_path = models.CharField(max_length=500)
    object_key = models.CharField(max_length=800, blank=True, default="")
    content_hash = models.CharField(max_length=64)
    index_status = models.CharField(
        max_length=20, choices=IndexStatus.choices, default=IndexStatus.PENDING
    )
    last_error = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def hash_content(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


class Chunk(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    file = models.ForeignKey(FileObject, on_delete=models.CASCADE)
    chunk_index = models.IntegerField()
    content = models.TextField()
    embedding = VectorField(dimensions=8)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("file", "chunk_index")

