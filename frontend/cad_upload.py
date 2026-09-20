"""Bounded staging and fail-closed validation for CAD multipart uploads."""

from __future__ import annotations

import hashlib
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from backend.interoperability.adapters._base import ContentSniffer

MAX_CAD_UPLOAD_BYTES = 64 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024
SNIFF_BYTES = 512

_EXTENSION_FAMILIES = {
    ".step": "STEP",
    ".stp": "STEP",
    ".p21": "STEP",
    ".iges": "IGES",
    ".igs": "IGES",
    ".dxf": "DXF",
}
_GENERIC_MEDIA_TYPES = frozenset({"application/octet-stream", "text/plain"})
_MEDIA_TYPE_FAMILIES = {
    "model/step": "STEP",
    "application/step": "STEP",
    "application/x-step": "STEP",
    "model/iges": "IGES",
    "application/iges": "IGES",
    "application/x-iges": "IGES",
    "image/vnd.dxf": "DXF",
    "application/dxf": "DXF",
    "application/x-dxf": "DXF",
    "image/x-dxf": "DXF",
}


class UploadReader(Protocol):
    filename: str | None
    content_type: str | None

    async def read(self, size: int) -> bytes: ...


@dataclass(frozen=True, slots=True)
class StagedCadUpload:
    """Safe metadata and a short-lived path for one validated upload."""

    path: Path
    filename: str
    content_type: str
    file_size: int
    sha256: str
    header_bytes: bytes
    detected_format: str


class UploadRejected(Exception):
    """A caller-safe upload rejection with an HTTP status code."""

    def __init__(self, status_code: int, safe_message: str) -> None:
        super().__init__(safe_message)
        self.status_code = status_code
        self.safe_message = safe_message


def _safe_filename(filename: str | None) -> str:
    if not filename or not filename.strip():
        raise UploadRejected(400, "No file was uploaded.")
    basename = PurePosixPath(filename.strip().replace("\\", "/")).name
    if basename in {"", ".", ".."}:
        raise UploadRejected(400, "No file was uploaded.")
    return basename


def _format_family(format_id: str) -> str | None:
    if format_id.startswith("STEP-"):
        return "STEP"
    if format_id in {"IGES", "DXF"}:
        return format_id
    return None


def _validate_format_signals(
    *, filename: str, content_type: str, header_bytes: bytes
) -> str:
    extension_family = _EXTENSION_FAMILIES.get(Path(filename).suffix.lower())
    if extension_family is None:
        raise UploadRejected(415, "Unsupported file extension for CAD upload.")

    detected_format = ContentSniffer.sniff(header_bytes)
    if detected_format == "DXF-BINARY":
        raise UploadRejected(415, "binary DXF parsing is unavailable.")
    detected_family = _format_family(detected_format or "")
    if detected_family is None:
        raise UploadRejected(415, "CAD file header is unsupported or invalid.")

    normalized_type = content_type.split(";", 1)[0].strip().lower()
    if normalized_type in _GENERIC_MEDIA_TYPES:
        media_family = extension_family
    else:
        media_family = _MEDIA_TYPE_FAMILIES.get(normalized_type)

    if media_family is None or not (
        extension_family == media_family == detected_family
    ):
        raise UploadRejected(415, "CAD file format signals do not match.")
    return detected_format or ""


@asynccontextmanager
async def stage_cad_upload(file: UploadReader) -> AsyncIterator[StagedCadUpload]:
    """Stage, hash, validate, yield, and always delete one CAD upload."""
    filename = _safe_filename(file.filename)
    content_type = (file.content_type or "").strip().lower()
    extension = Path(filename).suffix.lower()
    temporary = tempfile.NamedTemporaryFile(
        mode="w+b",
        suffix=extension,
        prefix="machiningpro-cad-",
        delete=False,
    )
    path = Path(temporary.name)
    digest = hashlib.sha256()
    header = bytearray()
    file_size = 0

    try:
        while True:
            chunk = await file.read(UPLOAD_CHUNK_BYTES)
            if not chunk:
                break
            file_size += len(chunk)
            if file_size > MAX_CAD_UPLOAD_BYTES:
                raise UploadRejected(413, "CAD upload exceeds the 64 MiB limit.")
            temporary.write(chunk)
            digest.update(chunk)
            if len(header) < SNIFF_BYTES:
                header.extend(chunk[: SNIFF_BYTES - len(header)])

        temporary.flush()
        temporary.close()

        if file_size == 0:
            raise UploadRejected(400, "The uploaded file is empty.")

        header_bytes = bytes(header)
        detected_format = _validate_format_signals(
            filename=filename,
            content_type=content_type,
            header_bytes=header_bytes,
        )
        yield StagedCadUpload(
            path=path,
            filename=filename,
            content_type=content_type,
            file_size=file_size,
            sha256=digest.hexdigest(),
            header_bytes=header_bytes,
            detected_format=detected_format,
        )
    finally:
        if not temporary.closed:
            temporary.close()
        path.unlink(missing_ok=True)


__all__ = [
    "MAX_CAD_UPLOAD_BYTES",
    "SNIFF_BYTES",
    "StagedCadUpload",
    "UPLOAD_CHUNK_BYTES",
    "UploadRejected",
    "stage_cad_upload",
]
