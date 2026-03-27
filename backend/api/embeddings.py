from __future__ import annotations

import hashlib
import math


def embed_8(text: str) -> list[float]:
    """
    MVP용 초간단/결정적 임베딩.
    추후 실제 임베딩 모델로 교체(재색인 필요).
    """
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vals = [(b - 128) / 128.0 for b in h[:8]]
    norm = math.sqrt(sum(v * v for v in vals)) or 1.0
    return [v / norm for v in vals]


def to_vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"

