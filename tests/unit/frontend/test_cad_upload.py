"""Safe streaming and validation tests for CAD multipart uploads."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from frontend.cad_upload import (
    MAX_CAD_UPLOAD_BYTES,
    UPLOAD_CHUNK_BYTES,
    UploadRejected,
    stage_cad_upload,
)

_STEP_HEADER = b"ISO-10303-21;\nHEADER;\n"
_IGES_HEADER = (b"A" * 72) + b"S      1\n"
_DXF_HEADER = b"  0\nSECTION\n  2\nHEADER\n"


@dataclass
class MemoryUpload:
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"
    offset: int = 0
    read_sizes: list[int] = field(default_factory=list)

    async def read(self, size: int) -> bytes:
        self.read_sizes.append(size)
        chunk = self.content[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


class RepeatingUpload:
    def __init__(self, *, total_size: int) -> None:
        self.filename = "limit.step"
        self.content_type = "application/octet-stream"
        self.total_size = total_size
        self.offset = 0
        self.read_sizes: list[int] = []
        self._fill = b"X" * UPLOAD_CHUNK_BYTES

    async def read(self, size: int) -> bytes:
        self.read_sizes.append(size)
        if self.offset >= self.total_size:
            return b""
        take = min(size, self.total_size - self.offset)
        chunk = bytearray(self._fill[:take])
        if self.offset < len(_STEP_HEADER):
            start = self.offset
            end = min(len(_STEP_HEADER), self.offset + take)
            chunk[: end - start] = _STEP_HEADER[start:end]
        self.offset += take
        return bytes(chunk)


def _stage(upload: object):
    async def run():
        async with stage_cad_upload(upload) as staged:
            assert staged.path.exists()
            return staged

    return asyncio.run(run())


class TestStreamingBoundary:
    def test_reads_only_bounded_chunks_and_hashes_content(self) -> None:
        content = _STEP_HEADER + b"POST_512" * 100
        upload = MemoryUpload("part.step", content)

        staged = _stage(upload)

        assert upload.read_sizes and set(upload.read_sizes) == {UPLOAD_CHUNK_BYTES}
        assert staged.file_size == len(content)
        assert staged.sha256 == hashlib.sha256(content).hexdigest()
        assert staged.header_bytes == content[:512]
        assert not staged.path.exists()

    def test_exactly_64_mib_is_accepted(self) -> None:
        upload = RepeatingUpload(total_size=MAX_CAD_UPLOAD_BYTES)

        staged = _stage(upload)

        expected = hashlib.sha256()
        first = bytearray(b"X" * UPLOAD_CHUNK_BYTES)
        first[: len(_STEP_HEADER)] = _STEP_HEADER
        expected.update(first)
        for _ in range((MAX_CAD_UPLOAD_BYTES // UPLOAD_CHUNK_BYTES) - 1):
            expected.update(b"X" * UPLOAD_CHUNK_BYTES)
        assert staged.file_size == MAX_CAD_UPLOAD_BYTES
        assert staged.sha256 == expected.hexdigest()
        assert not staged.path.exists()

    def test_first_byte_over_limit_is_413(self) -> None:
        upload = RepeatingUpload(total_size=MAX_CAD_UPLOAD_BYTES + 1)

        with pytest.raises(UploadRejected) as raised:
            _stage(upload)

        assert raised.value.status_code == 413
        assert "64 MiB" in raised.value.safe_message

    def test_cleanup_runs_when_context_body_raises(self) -> None:
        upload = MemoryUpload("part.step", _STEP_HEADER)
        staged_path: Path | None = None

        async def run() -> None:
            nonlocal staged_path
            with pytest.raises(RuntimeError, match="consumer failed"):
                async with stage_cad_upload(upload) as staged:
                    staged_path = staged.path
                    raise RuntimeError("consumer failed")

        asyncio.run(run())

        assert staged_path is not None
        assert not staged_path.exists()


class TestFormatSignalValidation:
    @pytest.mark.parametrize("extension", ["step", "stp", "p21"])
    def test_step_aliases_are_accepted(self, extension: str) -> None:
        staged = _stage(MemoryUpload(f"part.{extension}", _STEP_HEADER))
        assert staged.detected_format == "STEP-GENERIC"

    @pytest.mark.parametrize("extension", ["iges", "igs"])
    def test_iges_aliases_are_accepted(self, extension: str) -> None:
        staged = _stage(MemoryUpload(f"part.{extension}", _IGES_HEADER))
        assert staged.detected_format == "IGES"

    def test_ascii_dxf_is_accepted(self) -> None:
        staged = _stage(MemoryUpload("part.dxf", _DXF_HEADER, "image/vnd.dxf"))
        assert staged.detected_format == "DXF"

    @pytest.mark.parametrize(
        ("filename", "content", "content_type"),
        [
            ("part.step", _IGES_HEADER, "application/octet-stream"),
            ("part.dxf", _STEP_HEADER, "application/octet-stream"),
            ("part.step", _STEP_HEADER, "application/pdf"),
        ],
    )
    def test_signal_mismatch_is_rejected_without_content_leak(
        self, filename: str, content: bytes, content_type: str
    ) -> None:
        with pytest.raises(UploadRejected) as raised:
            _stage(MemoryUpload(filename, content, content_type))

        assert raised.value.status_code == 415
        assert content.decode("ascii", errors="ignore") not in raised.value.safe_message

    def test_unsupported_extension_is_rejected(self) -> None:
        with pytest.raises(UploadRejected) as raised:
            _stage(MemoryUpload("part.stl", b"solid model"))
        assert raised.value.status_code == 415

    def test_empty_upload_is_rejected(self) -> None:
        with pytest.raises(UploadRejected) as raised:
            _stage(MemoryUpload("part.step", b""))
        assert raised.value.status_code == 400

    def test_binary_dxf_is_unavailable(self) -> None:
        with pytest.raises(UploadRejected) as raised:
            _stage(MemoryUpload("part.dxf", b"AutoCAD Binary DXF\r\n", "application/dxf"))
        assert raised.value.status_code == 415
        assert "binary DXF" in raised.value.safe_message

    def test_caller_path_is_reduced_to_basename(self) -> None:
        staged = _stage(MemoryUpload("..\\unsafe\\part.step", _STEP_HEADER))
        assert staged.filename == "part.step"
        assert staged.path.name != "part.step"
