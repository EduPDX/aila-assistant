"""Leitura limitada de uploads, sem aceitar corpos arbitrariamente grandes."""

from __future__ import annotations

from fastapi import HTTPException, UploadFile


async def read_limited(file: UploadFile, max_mb: int) -> bytes:
    limit = max_mb * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(min(1024 * 1024, limit - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail=f"Arquivo excede {max_mb}MB.")
        chunks.append(chunk)
    return b"".join(chunks)
