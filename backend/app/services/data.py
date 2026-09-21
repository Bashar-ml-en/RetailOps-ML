"""Server-side CSV upload handling for authorised connector snapshots."""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import UploadFile

from app.services.validation import CsvBundle


class CsvInputError(ValueError):
    """Raised when a submitted connector file is not a safe CSV input."""


async def csv_bundle_from_uploads(
    uploads: Mapping[str, UploadFile | None], *, max_upload_bytes: int
) -> CsvBundle:
    """Read bounded CSV files without retaining an oversized upload in memory."""

    tables: dict[str, bytes] = {}
    for table, upload in uploads.items():
        if upload is None:
            continue
        filename = upload.filename or ""
        if not filename.lower().endswith(".csv"):
            raise CsvInputError(f"{table} must be a .csv file")
        chunks: list[bytes] = []
        total_bytes = 0
        while chunk := await upload.read(min(1_048_576, max_upload_bytes + 1)):
            total_bytes += len(chunk)
            if total_bytes > max_upload_bytes:
                raise CsvInputError(f"{table} exceeds the configured upload limit")
            chunks.append(chunk)
        if not chunks:
            raise CsvInputError(f"{table} is empty")
        tables[table] = b"".join(chunks)
    return CsvBundle(tables=tables)
