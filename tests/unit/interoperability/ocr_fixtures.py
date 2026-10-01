"""Deterministic, license-safe synthetic raster drawing fixtures.

This module intentionally uses only the Python standard library.  It creates
grayscale PNG bytes and minimal PDF image objects from generated pixels; no
font files, downloaded assets, OCR engine, or production decoder is involved.
Coordinates are top-left pixel coordinates for raster pages and are retained by
the fixture specs so later OCR/provenance tests can assert exact boxes.
"""

from __future__ import annotations

import binascii
import struct
import zlib
from dataclasses import dataclass

_MAX_TEXT_LENGTH = 128
_GLYPH_WIDTH = 5
_GLYPH_HEIGHT = 7

# A small public-domain-style bitmap alphabet authored as test data.  Glyphs
# are deliberately ASCII-only so rendering is independent of installed fonts.
_GLYPHS: dict[str, tuple[str, ...]] = {
    " ": ("00000",) * 7,
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00110", "00110"),
    "/": ("00001", "00010", "00100", "01000", "10000", "00000", "00000"),
    ":": ("00000", "00110", "00110", "00000", "00110", "00110", "00000"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
}
for _letter, _rows in {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
}.items():
    _GLYPHS[_letter] = _rows


def _validate_dimension(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int")
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _validate_coordinate(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True)
class RasterTextSpec:
    """ASCII text at an exact top-left raster coordinate."""

    text: str
    x: int
    y: int
    scale: int = 1
    foreground: int = 0

    def __post_init__(self) -> None:
        if not self.text or len(self.text) > _MAX_TEXT_LENGTH:
            raise ValueError("RasterTextSpec.text length is outside the supported bound")
        if any(character not in _GLYPHS for character in self.text.upper()):
            raise ValueError("RasterTextSpec.text must use the synthetic ASCII glyph set")
        _validate_coordinate("RasterTextSpec.x", self.x)
        _validate_coordinate("RasterTextSpec.y", self.y)
        _validate_dimension("RasterTextSpec.scale", self.scale)
        if not 0 <= self.foreground <= 255:
            raise ValueError("RasterTextSpec.foreground must be in [0, 255]")

    @property
    def width(self) -> int:
        return len(self.text) * (_GLYPH_WIDTH + 1) * self.scale - self.scale

    @property
    def height(self) -> int:
        return _GLYPH_HEIGHT * self.scale

    @property
    def bounding_box(self) -> tuple[int, int, int, int]:
        """Exact top-left raster box suitable for later provenance assertions."""

        return (self.x, self.y, self.x + self.width, self.y + self.height)


@dataclass(frozen=True)
class RasterLineSpec:
    x0: int
    y0: int
    x1: int
    y1: int
    value: int = 0

    def __post_init__(self) -> None:
        for name in ("x0", "y0", "x1", "y1"):
            _validate_coordinate(f"RasterLineSpec.{name}", getattr(self, name))
        if not 0 <= self.value <= 255:
            raise ValueError("RasterLineSpec.value must be in [0, 255]")


@dataclass(frozen=True)
class RasterRectSpec:
    x: int
    y: int
    width: int
    height: int
    value: int = 0

    def __post_init__(self) -> None:
        _validate_coordinate("RasterRectSpec.x", self.x)
        _validate_coordinate("RasterRectSpec.y", self.y)
        _validate_dimension("RasterRectSpec.width", self.width)
        _validate_dimension("RasterRectSpec.height", self.height)
        if not 0 <= self.value <= 255:
            raise ValueError("RasterRectSpec.value must be in [0, 255]")


@dataclass(frozen=True)
class SyntheticRasterImage:
    """Immutable grayscale raster plus deterministic PNG serialization."""

    width: int
    height: int
    pixels: bytes
    rotation: int = 0

    def __post_init__(self) -> None:
        _validate_dimension("SyntheticRasterImage.width", self.width)
        _validate_dimension("SyntheticRasterImage.height", self.height)
        if len(self.pixels) != self.width * self.height:
            raise ValueError("SyntheticRasterImage.pixels size must equal width*height")
        if self.rotation not in (0, 90, 180, 270):
            raise ValueError("SyntheticRasterImage.rotation must be 0, 90, 180, or 270")

    def png_bytes(self) -> bytes:
        """Return deterministic 8-bit grayscale PNG bytes (color type 0)."""

        rows = b"".join(
            b"\x00" + self.pixels[row * self.width : (row + 1) * self.width]
            for row in range(self.height)
        )
        return _png_bytes(self.width, self.height, 0, zlib.compress(rows, level=9))

    @property
    def image_object_id(self) -> str:
        """Stable fixture identity used by later provenance assertions."""

        return "synthetic:image:1"

    @staticmethod
    def image_object_id_for_page(page_number: int, image_index: int = 1) -> str:
        if page_number < 1 or image_index < 1:
            raise ValueError("page_number and image_index must be positive")
        return f"synthetic:page-{page_number}:image-{image_index}"


@dataclass(frozen=True)
class SyntheticRasterDrawingBuilder:
    """Build a deterministic synthetic technical-drawing raster page."""

    width: int = 640
    height: int = 480
    background: int = 255
    rotation: int = 0
    texts: tuple[RasterTextSpec, ...] = ()
    lines: tuple[RasterLineSpec, ...] = ()
    rectangles: tuple[RasterRectSpec, ...] = ()

    def __post_init__(self) -> None:
        _validate_dimension("SyntheticRasterDrawingBuilder.width", self.width)
        _validate_dimension("SyntheticRasterDrawingBuilder.height", self.height)
        if not 0 <= self.background <= 255:
            raise ValueError("background must be in [0, 255]")
        if self.rotation not in (0, 90, 180, 270):
            raise ValueError("rotation must be 0, 90, 180, or 270")
        for name, values, item_type in (
            ("texts", self.texts, RasterTextSpec),
            ("lines", self.lines, RasterLineSpec),
            ("rectangles", self.rectangles, RasterRectSpec),
        ):
            if not isinstance(values, tuple) or not all(
                isinstance(value, item_type) for value in values
            ):
                raise TypeError(f"{name} must be a tuple of {item_type.__name__}")

    def with_text(self, text: str, x: int, y: int, *, scale: int = 1, foreground: int = 0):
        return self._replace(
            texts=self.texts + (RasterTextSpec(text, x, y, scale, foreground),)
        )

    def with_line(self, x0: int, y0: int, x1: int, y1: int, *, value: int = 0):
        return self._replace(lines=self.lines + (RasterLineSpec(x0, y0, x1, y1, value),))

    def with_rectangle(self, x: int, y: int, width: int, height: int, *, value: int = 0):
        return self._replace(
            rectangles=self.rectangles + (RasterRectSpec(x, y, width, height, value),)
        )

    def title_block(self, x: int = 420, y: int = 350, width: int = 190, height: int = 110):
        builder = self.with_rectangle(x, y, width, height)
        return builder.with_text("TITLE BLOCK", x + 8, y + 8).with_text(
            "DWG 001", x + 8, y + 28
        )

    def ordinary_dimension(self, value: str = "25.0", x: int = 100, y: int = 100):
        return self.with_text(value, x, y)

    def ordinary_tolerance(self, value: str = "+/-0.1", x: int = 100, y: int = 125):
        return self.with_text(value, x, y)

    def datum_label(self, label: str = "A", x: int = 100, y: int = 155):
        return self.with_text(label, x, y)

    def gdt_frame(self, cells: tuple[str, ...] = ("FLAT", "0.1", "A"), x: int = 100, y: int = 190):
        builder = self
        cell_width = 58
        for index, cell in enumerate(cells):
            builder = builder.with_rectangle(x + index * cell_width, y, cell_width, 24)
            builder = builder.with_text(cell, x + 4 + index * cell_width, y + 8)
        return builder

    def _replace(self, **changes):
        values = {
            "width": self.width,
            "height": self.height,
            "background": self.background,
            "rotation": self.rotation,
            "texts": self.texts,
            "lines": self.lines,
            "rectangles": self.rectangles,
        }
        values.update(changes)
        return type(self)(**values)

    def build(self) -> SyntheticRasterImage:
        pixels = bytearray([self.background]) * (self.width * self.height)
        for rectangle in self.rectangles:
            _draw_rectangle(pixels, self.width, self.height, rectangle)
        for line in self.lines:
            _draw_line(pixels, self.width, self.height, line)
        for text in self.texts:
            _draw_text(pixels, self.width, self.height, text)
        if self.rotation:
            pixels, width, height = _rotate_pixels(
                bytes(pixels), self.width, self.height, self.rotation
            )
        else:
            width, height = self.width, self.height
        return SyntheticRasterImage(width, height, pixels, self.rotation)


@dataclass(frozen=True)
class SyntheticRasterPdfBuilder:
    """Build deterministic minimal PDFs containing generated grayscale images."""

    pages: tuple[SyntheticRasterImage, ...] = ()
    mixed_vector_pages: tuple[int, ...] = ()

    def add_page(self, image: SyntheticRasterImage, *, mixed_vector: bool = False):
        if not isinstance(image, SyntheticRasterImage):
            raise TypeError("image must be SyntheticRasterImage")
        pages = self.pages + (image,)
        mixed = self.mixed_vector_pages + ((len(pages),) if mixed_vector else ())
        return type(self)(pages, mixed)

    def build(self) -> bytes:
        objects: list[bytes] = []

        def reserve() -> int:
            objects.append(b"")
            return len(objects)

        def set_object(object_id: int, payload: bytes) -> None:
            objects[object_id - 1] = payload

        catalog_id = reserve()
        pages_id = reserve()
        page_records: list[tuple[int, int, int, SyntheticRasterImage, bool]] = []
        for index, image in enumerate(self.pages, start=1):
            page_id, content_id, image_id = reserve(), reserve(), reserve()
            page_records.append(
                (page_id, content_id, image_id, image, index in self.mixed_vector_pages)
            )
        set_object(catalog_id, f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())
        kids = " ".join(f"{page_id} 0 R" for page_id, *_ in page_records)
        set_object(
            pages_id,
            f"<< /Type /Pages /Kids [{kids}] /Count {len(page_records)} >>".encode(),
        )
        for page_id, content_id, image_id, image, mixed in page_records:
            raw = b"".join(
                image.pixels[row * image.width : (row + 1) * image.width]
                for row in range(image.height)
            )
            compressed = zlib.compress(raw, level=9)
            image_object = (
                f"<< /Type /XObject /Subtype /Image /Width {image.width} "
                f"/Height {image.height} /ColorSpace /DeviceGray "
                f"/BitsPerComponent 8 /Filter /FlateDecode /Length {len(compressed)} >>\n"
            ).encode() + b"stream\n" + compressed + b"\nendstream"
            set_object(image_id, image_object)
            content = b"q\n" + f"{image.width} 0 0 {image.height} 0 0 cm\n/Im1 Do\nQ\n".encode()
            if mixed:
                content += b"q\n1 w\n10 10 m\n100 10 l\nS\nQ\n"
            set_object(
                content_id,
                f"<< /Length {len(content)} >>\nstream\n".encode()
                + content
                + b"endstream",
            )
            page_payload = (
                f"<< /Type /Page /Parent {pages_id} 0 R "
                f"/MediaBox [0 0 {image.width} {image.height}] "
                f"{('/Rotate ' + str(image.rotation)) if image.rotation else ''} "
                f"/Resources << /XObject << /Im1 {image_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode()
            set_object(page_id, page_payload)
        return _serialize_pdf(objects, catalog_id)


def malformed_png_bytes() -> bytes:
    """Return a deterministic truncated PNG for decoder failure tests."""

    image = SyntheticRasterDrawingBuilder(width=8, height=8).build().png_bytes()
    return image[:-7]


def oversized_png_header(width: int = 20_001, height: int = 20_001) -> bytes:
    """Return a tiny PNG header advertising oversized dimensions safely."""

    return _png_bytes(width, height, 0, b"", include_iend=False)


def _png_bytes(
    width: int,
    height: int,
    color_type: int,
    compressed: bytes,
    *,
    include_iend: bool = True,
) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    output = bytearray(signature)
    output.extend(_png_chunk(b"IHDR", ihdr))
    if compressed:
        output.extend(_png_chunk(b"IDAT", compressed))
    if include_iend:
        output.extend(_png_chunk(b"IEND", b""))
    return bytes(output)


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    payload = chunk_type + data
    crc = struct.pack(">I", binascii.crc32(payload) & 0xFFFFFFFF)
    return struct.pack(">I", len(data)) + payload + crc


def _draw_rectangle(pixels: bytearray, width: int, height: int, spec: RasterRectSpec) -> None:
    for x in range(spec.x, min(width, spec.x + spec.width)):
        _set_pixel(pixels, width, height, x, spec.y, spec.value)
        _set_pixel(pixels, width, height, x, spec.y + spec.height - 1, spec.value)
    for y in range(spec.y, min(height, spec.y + spec.height)):
        _set_pixel(pixels, width, height, spec.x, y, spec.value)
        _set_pixel(pixels, width, height, spec.x + spec.width - 1, y, spec.value)


def _draw_line(pixels: bytearray, width: int, height: int, spec: RasterLineSpec) -> None:
    dx, dy = abs(spec.x1 - spec.x0), abs(spec.y1 - spec.y0)
    sx = 1 if spec.x0 < spec.x1 else -1
    sy = 1 if spec.y0 < spec.y1 else -1
    error = dx - dy
    x, y = spec.x0, spec.y0
    while True:
        _set_pixel(pixels, width, height, x, y, spec.value)
        if x == spec.x1 and y == spec.y1:
            break
        doubled = 2 * error
        if doubled > -dy:
            error -= dy
            x += sx
        if doubled < dx:
            error += dx
            y += sy


def _draw_text(pixels: bytearray, width: int, height: int, spec: RasterTextSpec) -> None:
    cursor_x = spec.x
    for character in spec.text.upper():
        glyph = _GLYPHS[character]
        for row, pattern in enumerate(glyph):
            for column, bit in enumerate(pattern):
                if bit == "1":
                    for dy in range(spec.scale):
                        for dx in range(spec.scale):
                            _set_pixel(
                                pixels,
                                width,
                                height,
                                cursor_x + column * spec.scale + dx,
                                spec.y + row * spec.scale + dy,
                                spec.foreground,
                            )
        cursor_x += (_GLYPH_WIDTH + 1) * spec.scale


def _set_pixel(pixels: bytearray, width: int, height: int, x: int, y: int, value: int) -> None:
    if 0 <= x < width and 0 <= y < height:
        pixels[y * width + x] = value


def _rotate_pixels(pixels: bytes, width: int, height: int, rotation: int) -> tuple[bytes, int, int]:
    if rotation in (0, 180):
        result_width, result_height = width, height
    else:
        result_width, result_height = height, width
    output = bytearray(result_width * result_height)
    for y in range(height):
        for x in range(width):
            if rotation == 90:
                target_x, target_y = height - 1 - y, x
            elif rotation == 180:
                target_x, target_y = width - 1 - x, height - 1 - y
            elif rotation == 270:
                target_x, target_y = y, width - 1 - x
            else:
                target_x, target_y = x, y
            output[target_y * result_width + target_x] = pixels[y * width + x]
    return bytes(output), result_width, result_height


def _serialize_pdf(objects: list[bytes], catalog_id: int) -> bytes:
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id, payload in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode())
        output.extend(payload)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(output)


__all__ = [
    "RasterLineSpec",
    "RasterRectSpec",
    "RasterTextSpec",
    "SyntheticRasterDrawingBuilder",
    "SyntheticRasterImage",
    "SyntheticRasterPdfBuilder",
    "malformed_png_bytes",
    "oversized_png_header",
]
