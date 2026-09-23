"""License-safe deterministic PDF fixtures for drawing-parser tests.

The builder writes a minimal PDF 1.4 document using only synthetic values
supplied by tests. Coordinates use the native PDF bottom-left origin so the
serialized vector operators are exact; pdfplumber later exposes its normalized
top-left coordinates for canonical provenance assertions.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


def _validate_decimal(name: str, value: Decimal) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal, got {type(value)}")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")


def _pdf_number(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _pdf_literal(text: str) -> bytes:
    try:
        encoded = text.encode("cp1252")
    except UnicodeEncodeError as exc:
        raise ValueError("synthetic PDF text must be representable in WinAnsi") from exc

    escaped = bytearray()
    for value in encoded:
        if value in (ord("("), ord(")"), ord("\\")):
            escaped.extend(b"\\")
            escaped.append(value)
        elif value < 32 or value > 126:
            escaped.extend(f"\\{value:03o}".encode("ascii"))
        else:
            escaped.append(value)
    return bytes(escaped)


@dataclass(frozen=True)
class PdfTextSpec:
    """One synthetic vector-text run at an exact PDF baseline coordinate."""

    text: str
    x: Decimal
    y: Decimal
    font_size: Decimal = Decimal("12")

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text:
            raise ValueError("PdfTextSpec.text must be a non-empty string")
        if any(ord(character) < 32 for character in self.text):
            raise ValueError("PdfTextSpec.text must not contain control characters")
        _validate_decimal("PdfTextSpec.x", self.x)
        _validate_decimal("PdfTextSpec.y", self.y)
        _validate_decimal("PdfTextSpec.font_size", self.font_size)
        if self.font_size <= 0:
            raise ValueError("PdfTextSpec.font_size must be positive")


@dataclass(frozen=True)
class PdfLineSpec:
    """One synthetic stroked line in native PDF coordinates."""

    x0: Decimal
    y0: Decimal
    x1: Decimal
    y1: Decimal
    line_width: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        for name in ("x0", "y0", "x1", "y1", "line_width"):
            _validate_decimal(f"PdfLineSpec.{name}", getattr(self, name))
        if self.line_width <= 0:
            raise ValueError("PdfLineSpec.line_width must be positive")


@dataclass(frozen=True)
class PdfRectSpec:
    """One synthetic stroked rectangle in native PDF coordinates."""

    x0: Decimal
    y0: Decimal
    x1: Decimal
    y1: Decimal
    line_width: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        for name in ("x0", "y0", "x1", "y1", "line_width"):
            _validate_decimal(f"PdfRectSpec.{name}", getattr(self, name))
        if self.x0 > self.x1:
            raise ValueError("PdfRectSpec.x0 must be <= x1")
        if self.y0 > self.y1:
            raise ValueError("PdfRectSpec.y0 must be <= y1")
        if self.line_width <= 0:
            raise ValueError("PdfRectSpec.line_width must be positive")


@dataclass(frozen=True)
class _PdfPageSpec:
    width_pt: int
    height_pt: int
    rotation: int
    texts: tuple[PdfTextSpec, ...]
    lines: tuple[PdfLineSpec, ...]
    rectangles: tuple[PdfRectSpec, ...]
    include_image: bool


class SyntheticPdfBuilder:
    """Build byte-identical minimal PDFs from explicit synthetic vector data."""

    def __init__(self) -> None:
        self._pages: list[_PdfPageSpec] = []

    def add_vector_page(
        self,
        *,
        width_pt: int = 842,
        height_pt: int = 595,
        rotation: int = 0,
        texts: tuple[PdfTextSpec, ...] = (),
        lines: tuple[PdfLineSpec, ...] = (),
        rectangles: tuple[PdfRectSpec, ...] = (),
        include_image: bool = False,
    ) -> None:
        """Append a synthetic page in stable caller-provided object order."""

        for name, value in (("width_pt", width_pt), ("height_pt", height_pt)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be int")
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if rotation not in (0, 90, 180, 270):
            raise ValueError("rotation must be one of 0, 90, 180, or 270")
        collections = (
            ("texts", texts, PdfTextSpec),
            ("lines", lines, PdfLineSpec),
            ("rectangles", rectangles, PdfRectSpec),
        )
        for name, values, item_type in collections:
            if not isinstance(values, tuple):
                raise TypeError(f"{name} must be a tuple")
            if not all(isinstance(value, item_type) for value in values):
                raise TypeError(f"{name} must contain only {item_type.__name__} values")
        if not isinstance(include_image, bool):
            raise TypeError("include_image must be bool")

        self._pages.append(
            _PdfPageSpec(
                width_pt=width_pt,
                height_pt=height_pt,
                rotation=rotation,
                texts=texts,
                lines=lines,
                rectangles=rectangles,
                include_image=include_image,
            )
        )

    def build(self) -> bytes:
        """Serialize the current synthetic pages as a deterministic PDF 1.4."""

        objects: list[bytes] = []

        def reserve_object() -> int:
            objects.append(b"")
            return len(objects)

        def set_object(object_id: int, payload: bytes) -> None:
            objects[object_id - 1] = payload

        catalog_id = reserve_object()
        pages_id = reserve_object()
        font_id = reserve_object()
        page_records: list[tuple[int, int, int | None, _PdfPageSpec]] = []

        for page in self._pages:
            page_id = reserve_object()
            content_id = reserve_object()
            image_id = reserve_object() if page.include_image else None
            page_records.append((page_id, content_id, image_id, page))

        set_object(catalog_id, f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii"))
        kids = " ".join(f"{page_id} 0 R" for page_id, _, _, _ in page_records)
        set_object(
            pages_id,
            f"<< /Type /Pages /Kids [{kids}] /Count {len(page_records)} >>".encode("ascii"),
        )
        set_object(
            font_id,
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding >>",
        )

        for page_id, content_id, image_id, page in page_records:
            content = self._page_content(page, image_id is not None)
            set_object(
                content_id,
                f"<< /Length {len(content)} >>\nstream\n".encode("ascii")
                + content
                + b"endstream",
            )
            if image_id is not None:
                image_data = b"\x00"
                set_object(
                    image_id,
                    b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 "
                    b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Length 1 >>\n"
                    b"stream\n"
                    + image_data
                    + b"\nendstream",
                )

            resources = f"<< /Font << /F1 {font_id} 0 R >>"
            if image_id is not None:
                resources += f" /XObject << /Im1 {image_id} 0 R >>"
            resources += " >>"
            rotation = f" /Rotate {page.rotation}" if page.rotation else ""
            page_payload = (
                f"<< /Type /Page /Parent {pages_id} 0 R "
                f"/MediaBox [0 0 {page.width_pt} {page.height_pt}]"
                f"{rotation} /Resources {resources} /Contents {content_id} 0 R >>"
            )
            set_object(page_id, page_payload.encode("ascii"))

        return self._serialize(objects, catalog_id)

    @staticmethod
    def _page_content(page: _PdfPageSpec, include_image: bool) -> bytes:
        commands: list[bytes] = []
        for text in page.texts:
            commands.append(
                b"BT\n/F1 "
                + _pdf_number(text.font_size).encode("ascii")
                + b" Tf\n1 0 0 1 "
                + _pdf_number(text.x).encode("ascii")
                + b" "
                + _pdf_number(text.y).encode("ascii")
                + b" Tm\n("
                + _pdf_literal(text.text)
                + b") Tj\nET\n"
            )
        for line in page.lines:
            commands.append(
                (
                    "q\n"
                    f"{_pdf_number(line.line_width)} w\n"
                    f"{_pdf_number(line.x0)} {_pdf_number(line.y0)} m\n"
                    f"{_pdf_number(line.x1)} {_pdf_number(line.y1)} l\n"
                    "S\nQ\n"
                ).encode("ascii")
            )
        for rectangle in page.rectangles:
            width = rectangle.x1 - rectangle.x0
            height = rectangle.y1 - rectangle.y0
            commands.append(
                (
                    "q\n"
                    f"{_pdf_number(rectangle.line_width)} w\n"
                    f"{_pdf_number(rectangle.x0)} {_pdf_number(rectangle.y0)} "
                    f"{_pdf_number(width)} {_pdf_number(height)} re\n"
                    "S\nQ\n"
                ).encode("ascii")
            )
        if include_image:
            commands.append(b"q\n1 0 0 1 0 0 cm\n/Im1 Do\nQ\n")
        return b"".join(commands)

    @staticmethod
    def _serialize(objects: list[bytes], catalog_id: int) -> bytes:
        output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for object_id, payload in enumerate(objects, start=1):
            offsets.append(len(output))
            output.extend(f"{object_id} 0 obj\n".encode("ascii"))
            output.extend(payload)
            output.extend(b"\nendobj\n")

        xref_offset = len(output)
        output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        output.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        output.extend(
            (
                f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
                f"startxref\n{xref_offset}\n%%EOF\n"
            ).encode("ascii")
        )
        return bytes(output)


__all__ = [
    "PdfLineSpec",
    "PdfRectSpec",
    "PdfTextSpec",
    "SyntheticPdfBuilder",
]
