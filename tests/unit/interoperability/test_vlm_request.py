"""Phase 1D R3D: bounded, deterministic, explicit request preparation."""

from __future__ import annotations

import ast
import builtins
import hashlib
import itertools
import json
import pickle
import re
import socket
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

import backend.interoperability.ocr_drawing as ocr_drawing
import backend.interoperability.pdf_drawing as pdf_drawing
import backend.interoperability.raster_drawing as raster_drawing
import backend.interoperability.vlm_request as vlm_request
from backend.interoperability.drawing import (
    CanonicalDrawing,
    DrawingBoundingBox,
    DrawingDimension,
    DrawingDimensionType,
    DrawingExtractionAuthority,
    DrawingIngestionDiagnostics,
    DrawingIngestionResult,
    DrawingIngestionStatus,
    DrawingParserIdentity,
    DrawingRasterSource,
    DrawingSourceLocation,
)
from backend.interoperability.raster_drawing import RasterLimits, inspect_raster_pdf
from backend.interoperability.vlm_assist import AiAssistedDrawingExtractor
from backend.interoperability.vlm_drawing import (
    DrawingVlmAssistConfig,
    DrawingVlmMode,
    DrawingVlmRegion,
    DrawingVlmRegionKind,
    VlmLimits,
)
from backend.interoperability.vlm_provider import VlmTaskKind
from backend.interoperability.vlm_providers import MockVlmProvider
from backend.interoperability.vlm_request import (
    PreparedVlmRequest,
    VlmPreparationConfig,
    VlmPreparationError,
    VlmPreparationErrorCode,
    extractor_inputs,
    prepare_vlm_requests,
)
from backend.interoperability.vlm_response import VLM_RESPONSE_SCHEMA_VERSION
from tests.unit.interoperability.ocr_fixtures import (
    SyntheticRasterDrawingBuilder,
    SyntheticRasterPdfBuilder,
)

_SOURCE_ID = "upload::r3d.pdf"
_PROMPT = "machiningpro.drawing-vlm.v1"
_MODEL = MockVlmProvider().identity()
_E = VlmPreparationErrorCode
_WIDTH, _HEIGHT = 200, 100


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("network access is forbidden in R3D tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


def _pdf(pages: int = 1) -> bytes:
    builder = SyntheticRasterPdfBuilder()
    for index in range(pages):
        image = (
            SyntheticRasterDrawingBuilder(width=_WIDTH, height=_HEIGHT)
            .with_text("A", 20 + index, 20, scale=4)
            .build()
        )
        builder = builder.add_page(image)
    return builder.build()


_PDF = _pdf()


def _raster(page: int = 1, pdf: bytes | None = None) -> DrawingRasterSource:
    snapshot = inspect_raster_pdf(pdf or _PDF, _SOURCE_ID).snapshot
    return snapshot.pages[page - 1].images[0].raster_source


def _box(x0, top, x1, bottom) -> DrawingBoundingBox:
    return DrawingBoundingBox(Decimal(x0), Decimal(top), Decimal(x1), Decimal(bottom))


def _region(
    region_id: str = "vlm-region-1",
    *,
    crop=(10, 20, 110, 70),
    page: int = 1,
    triggers: tuple[str, ...] = ("t1",),
    pdf=None,
    raster: DrawingRasterSource | None = None,
) -> DrawingVlmRegion:
    x0, y0, x1, y1 = crop
    return DrawingVlmRegion(
        region_id=region_id,
        kind=DrawingVlmRegionKind.OCR_REVIEW,
        page_number=page,
        raster_source=raster or _raster(page, pdf),
        crop_px=crop,
        pdf_box=_box(x0, y0, x1, y1),
        trigger_evidence_ids=triggers,
    )


def _dimension(dimension_id="pdf-dim-1", *, text="25 mm", ids=("t1",), page=1):
    return DrawingDimension(
        dimension_id=dimension_id,
        nominal_value=Decimal("25"),
        unit="mm",
        dimension_type=DrawingDimensionType.LINEAR,
        source_location=DrawingSourceLocation(
            source_id=_SOURCE_ID,
            page_number=page,
            original_text=text,
            adapter_id="tesseract-ocr",
            adapter_version="1",
            authority=DrawingExtractionAuthority.EXTRACTED,
            source_object_ids=ids,
        ),
    )


def _base(*dimensions: DrawingDimension) -> DrawingIngestionResult:
    return DrawingIngestionResult(
        source_id=_SOURCE_ID,
        diagnostics=DrawingIngestionDiagnostics(
            status=DrawingIngestionStatus.VALID,
            format_detected="PDF",
            parser_id="machiningpro.vector-pdf",
            parser_version="1.0.0",
        ),
        document=CanonicalDrawing(
            drawing_id="pdf-drawing-r3d", source_id=_SOURCE_ID, all_dimensions=tuple(dimensions)
        ),
    )


def _config(**overrides) -> VlmPreparationConfig:
    values = {"prompt_contract_version": _PROMPT, "model": _MODEL}
    values.update(overrides)
    return VlmPreparationConfig(**values)


def _prepare(regions=None, *, base=None, pdf=None, **config):
    return prepare_vlm_requests(
        base or _base(),
        pdf if pdf is not None else _PDF,
        [_region()] if regions is None else regions,
        config=_config(**config),
    )


def _rejected(code, regions=None, **kwargs) -> None:
    with pytest.raises(VlmPreparationError) as raised:
        _prepare(regions, **kwargs)
    assert raised.value.code is code


# ---------------------------------------------------------------------------
# T01 / T02 / T17 / T18 / T19 / T20 / T21 — happy path, identity, hash, order
# ---------------------------------------------------------------------------


class TestPreparedRequests:
    def test_t01_valid_explicit_region_creates_a_bounded_request(self):
        (item,) = _prepare()
        request = item.request
        assert request.image_png.startswith(b"\x89PNG\r\n\x1a\n")
        assert (request.image_width_px, request.image_height_px) == (100, 50)
        assert request.model == _MODEL
        assert request.task_kind is VlmTaskKind.TRANSCRIBE
        assert request.context_text == ()
        assert request.max_response_bytes == VlmLimits().response_bytes
        assert len(request.image_png) <= VlmLimits().crop_png_bytes
        assert item.region == _region()

    def test_the_prepared_crop_is_exactly_the_selected_pixels(self):
        from io import BytesIO

        from PIL import Image

        (item,) = _prepare()
        with Image.open(BytesIO(item.request.image_png)) as png:
            assert png.mode == "L" and png.size == (100, 50)
            cropped = png.tobytes()
        pixels = SyntheticRasterDrawingBuilder(width=_WIDTH, height=_HEIGHT).with_text(
            "A", 20, 20, scale=4
        ).build().pixels
        expected = b"".join(
            pixels[row * _WIDTH + 10 : row * _WIDTH + 110] for row in range(20, 70)
        )
        assert cropped == expected

    def test_t02_repeated_identical_input_is_deterministic(self):
        assert _prepare() == _prepare()
        assert _prepare()[0].request.request_id == _prepare()[0].request.request_id

    def test_t17_payload_hash_is_sha256_of_the_exact_payload(self):
        (item,) = _prepare()
        assert item.payload_sha256 == hashlib.sha256(item.request.image_png).hexdigest()
        with pytest.raises(ValueError):
            replace(item, payload_sha256="0" * 64)
        with pytest.raises(ValueError):
            replace(item, payload_sha256="XYZ")

    def test_t18_ordering_is_independent_of_input_order(self):
        regions = [
            _region("vlm-region-b", crop=(0, 0, 50, 50)),
            _region("vlm-region-a", crop=(60, 0, 110, 50)),
            _region("vlm-region-c", crop=(0, 50, 50, 100)),
        ]
        baseline = _prepare(regions)
        assert [item.region.region_id for item in baseline] == [
            "vlm-region-a",
            "vlm-region-b",
            "vlm-region-c",
        ]
        for order in itertools.permutations(regions):
            assert _prepare(list(order)) == baseline

    def test_ordering_sorts_by_page_then_region(self):
        pdf = _pdf(2)
        regions = [
            _region("vlm-region-z", page=1, pdf=pdf),
            _region("vlm-region-a", page=2, pdf=pdf),
        ]
        prepared = _prepare(regions, pdf=pdf)
        assert [(i.region.page_number, i.region.region_id) for i in prepared] == [
            (1, "vlm-region-z"),
            (2, "vlm-region-a"),
        ]

    def test_t19_source_provenance_is_retained(self):
        (item,) = _prepare()
        assert item.region.raster_source.source_id == _SOURCE_ID
        assert item.region.page_number == 1
        assert item.region.raster_source.image_object_id == "page-1:image-1"
        assert item.region.trigger_evidence_ids == ("t1",)

    def test_t20_t21_prompt_and_schema_versions_are_bound(self):
        (item,) = _prepare()
        assert item.request.prompt_contract_version == _PROMPT
        assert item.schema_version == VLM_RESPONSE_SCHEMA_VERSION
        other_prompt = _prepare(prompt_contract_version="other.contract.v2")[0]
        assert other_prompt.request.request_id != item.request.request_id

    def test_request_identity_depends_on_every_explicit_input(self):
        base = _prepare()[0].request.request_id
        assert _prepare([_region("vlm-region-2")])[0].request.request_id != base
        assert _prepare([_region(crop=(11, 20, 111, 70))])[0].request.request_id != base
        gdt = _prepare(task_kind=VlmTaskKind.GDT_CHARACTERISTIC)[0].request.request_id
        assert gdt != base
        assert re.fullmatch(r"vlm-req-[0-9a-f]{32}", base)

    def test_request_id_has_no_time_or_randomness_dependence(self, monkeypatch):
        first = _prepare()[0].request.request_id
        import random
        import time
        import uuid

        for module, name in ((random, "random"), (time, "time"), (uuid, "uuid4")):
            monkeypatch.setattr(module, name, lambda *a, **k: 1 / 0)
        assert _prepare()[0].request.request_id == first

    def test_extractor_inputs_shape_and_end_to_end_with_the_mock_provider(self):
        prepared = _prepare()
        requests, regions = extractor_inputs(prepared)
        request = requests[0]
        body = {
            "schema_version": VLM_RESPONSE_SCHEMA_VERSION,
            "request_id": request.request_id,
            "prompt_contract_version": _PROMPT,
            "provider_id": _MODEL.provider_id,
            "model_id": _MODEL.model_id,
            "model_version": _MODEL.model_version,
            "items": [
                {
                    "candidate_type": "DIMENSION",
                    "value": "25 mm",
                    "legibility": "CLEAR",
                    "box": [0, 0, 50, 25],
                    "confidence": 0.9,
                    "evidence_reference": "t1",
                }
            ],
        }
        provider = MockVlmProvider([json.dumps(body).encode()])
        base = _base(_dimension())
        before = repr(base)
        outcome = AiAssistedDrawingExtractor(provider).extract_candidates(
            base,
            list(requests),
            config=DrawingVlmAssistConfig(enabled=True),
            regions=regions,
            reconcile=True,
        )
        assert outcome.advisory.status is DrawingIngestionStatus.VALID
        assert outcome.advisory.evidence[0].raw_candidate == "25 mm"
        assert repr(base) == before and outcome.result is base


# ---------------------------------------------------------------------------
# T03–T10 — explicit, valid regions only
# ---------------------------------------------------------------------------


class TestRegionValidation:
    def test_t03_no_regions_fails_closed_and_nothing_is_selected_automatically(self):
        _rejected(_E.NO_REGIONS, [])
        with pytest.raises(TypeError):
            prepare_vlm_requests(_base(), _PDF, None, config=_config())  # type: ignore[arg-type]

    def test_t03_pdf_content_is_never_used_to_invent_regions(self, monkeypatch):
        calls: list[str] = []
        monkeypatch.setattr(
            vlm_request, "prepare_raster_ocr_inputs", lambda *a, **k: calls.append("decode")
        )
        _rejected(_E.NO_REGIONS, [])
        assert calls == []

    def test_t04_negative_or_zero_page_cannot_be_constructed(self):
        for page in (-1, 0):
            with pytest.raises(ValueError):
                replace(_region(), page_number=page)

    def test_t05_out_of_range_page_is_rejected(self):
        far = replace(_raster(), page_number=5)
        _rejected(_E.REGION_SOURCE_NOT_FOUND, [_region(page=5, raster=far)])

    @pytest.mark.parametrize(
        "crop",
        [(-1, 0, 10, 10), (0, -1, 10, 10), (-5, -5, -1, -1)],
    )
    def test_t06_negative_coordinates_cannot_be_constructed(self, crop):
        with pytest.raises(ValueError):
            _region(crop=crop)

    @pytest.mark.parametrize("crop", [(10, 0, 5, 10), (0, 10, 10, 5)])
    def test_t07_inverted_regions_cannot_be_constructed(self, crop):
        with pytest.raises(ValueError):
            _region(crop=crop)

    @pytest.mark.parametrize("crop", [(5, 5, 5, 10), (5, 5, 10, 5), (5, 5, 5, 5)])
    def test_t08_zero_size_regions_cannot_be_constructed(self, crop):
        with pytest.raises(ValueError):
            _region(crop=crop)

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
    def test_t09_non_finite_geometry_cannot_be_constructed(self, value):
        with pytest.raises(ValueError):
            DrawingBoundingBox(Decimal(value), Decimal("0"), Decimal("1"), Decimal("1"))

    def test_t09_non_decimal_geometry_is_rejected(self):
        with pytest.raises(TypeError):
            DrawingBoundingBox(0.0, Decimal("0"), Decimal("1"), Decimal("1"))  # type: ignore[arg-type]

    def test_t10_crop_outside_the_image_is_rejected(self):
        _rejected(_E.REGION_OUTSIDE_IMAGE, [_region(crop=(150, 20, 250, 70))])
        _rejected(_E.REGION_OUTSIDE_IMAGE, [_region(crop=(10, 60, 110, 120))])

    def test_t10_pdf_box_outside_the_image_area_is_rejected(self):
        region = replace(_region(), pdf_box=_box(10, 20, 500, 70))
        _rejected(_E.REGION_OUTSIDE_PAGE_AREA, [region])
        region = replace(_region(), pdf_box=_box(-5, 20, 110, 70))
        _rejected(_E.REGION_OUTSIDE_PAGE_AREA, [region])

    def test_duplicate_region_ids_are_rejected_even_when_identical(self):
        _rejected(_E.DUPLICATE_REGION_ID, [_region(), _region()])
        _rejected(_E.DUPLICATE_REGION_ID, [_region(), _region(crop=(0, 0, 20, 20))])

    def test_first_valid_region_never_wins(self):
        good, bad = _region("vlm-region-a"), _region("vlm-region-b", crop=(150, 20, 250, 70))
        _rejected(_E.REGION_OUTSIDE_IMAGE, [good, bad])
        _rejected(_E.REGION_OUTSIDE_IMAGE, [bad, good])

    def test_overlapping_regions_stay_separate_requests(self):
        prepared = _prepare(
            [
                _region("vlm-region-a", crop=(0, 0, 60, 60)),
                _region("vlm-region-b", crop=(30, 30, 90, 90)),
            ]
        )
        assert len(prepared) == 2

    def test_region_for_a_different_source_is_rejected(self):
        other = replace(_raster(), source_id="upload::other.pdf")
        _rejected(_E.SOURCE_MISMATCH, [_region(raster=other)])

    def test_region_naming_an_unknown_image_or_altered_raster_source_is_rejected(self):
        unknown = replace(_raster(), image_object_id="page-1:image-9")
        _rejected(_E.REGION_SOURCE_NOT_FOUND, [_region(raster=unknown)])
        altered = replace(_raster(), bounding_box=_box(0, 0, 10, 10))
        _rejected(_E.REGION_SOURCE_MISMATCH, [_region(raster=altered)])


# ---------------------------------------------------------------------------
# T11–T16 — image safety and limits
# ---------------------------------------------------------------------------


class TestLimitsAndImageSafety:
    def test_t11_malformed_image_is_rejected(self):
        import zlib

        image = (
            SyntheticRasterDrawingBuilder(width=_WIDTH, height=_HEIGHT)
            .with_text("A", 20, 20, scale=4)
            .build()
        )
        compressed = zlib.compress(image.pixels, level=9)
        assert compressed in _PDF
        _rejected(_E.RASTER_MALFORMED, pdf=_PDF.replace(compressed, b"bad", 1))

    def test_t12_declared_and_actual_size_mismatch_is_rejected(self):
        mismatch = _PDF.replace(b"/Width 200 /Height 100", b"/Width 100 /Height 100", 1)
        assert mismatch != _PDF
        _rejected(_E.RASTER_MALFORMED, pdf=mismatch)

    def test_unsupported_filter_and_non_pdf_are_rejected(self):
        unsupported = _PDF.replace(b"/Filter /FlateDecode", b"/Filter /ASCII85Decode", 1)
        _rejected(_E.RASTER_UNSUPPORTED, pdf=unsupported)
        _rejected(_E.RASTER_UNSUPPORTED, pdf=b"not a pdf")

    def test_pdf_input_must_be_bytes_not_a_path(self, monkeypatch):
        def _no_open(*args, **kwargs):
            raise AssertionError("filesystem access attempted")

        monkeypatch.setattr(builtins, "open", _no_open)
        with pytest.raises(VlmPreparationError) as raised:
            prepare_vlm_requests(
                _base(), "C:/secret/drawing.pdf", [_region()], config=_config()  # type: ignore[arg-type]
            )
        assert raised.value.code is _E.PDF_INPUT_INVALID
        assert len(_prepare()) == 1  # normal preparation also never opens a file

    def test_t13_encoded_payload_over_limit_is_rejected(self):
        _rejected(_E.PNG_TOO_LARGE, limits=VlmLimits(crop_png_bytes=10))

    def test_t14_pixel_limits_apply_before_any_decode(self, monkeypatch):
        calls: list[str] = []
        original = vlm_request.prepare_raster_ocr_inputs
        monkeypatch.setattr(
            vlm_request,
            "prepare_raster_ocr_inputs",
            lambda *a, **k: (calls.append("decode"), original(*a, **k))[1],
        )
        _rejected(_E.CROP_PIXEL_LIMIT, limits=VlmLimits(crop_pixels=100))
        _rejected(_E.CROP_EDGE_LIMIT, limits=VlmLimits(crop_longest_edge_px=64))
        assert calls == []

    def test_t14_raster_limits_are_reused_for_source_images(self):
        _rejected(_E.RASTER_LIMIT, raster_limits=RasterLimits(max_pixels_per_image=1))
        _rejected(_E.RASTER_LIMIT, raster_limits=RasterLimits(max_width=10))
        _rejected(_E.RASTER_LIMIT, raster_limits=RasterLimits(max_file_bytes=10))

    def test_t15_request_count_limit_is_enforced(self):
        regions = [_region("vlm-region-a"), _region("vlm-region-b", crop=(0, 0, 40, 40))]
        _rejected(_E.REQUEST_LIMIT, regions, limits=VlmLimits(requests_per_document=1))

    def test_t16_region_count_limits_are_enforced(self):
        regions = [_region("vlm-region-a"), _region("vlm-region-b", crop=(0, 0, 40, 40))]
        _rejected(_E.REGION_LIMIT, regions, limits=VlmLimits(regions_per_page=1, regions_total=1))
        _rejected(_E.PAGE_REGION_LIMIT, regions, limits=VlmLimits(regions_per_page=1))

    def test_total_payload_cap_is_explicit_and_enforced_when_set(self):
        regions = [_region("vlm-region-a"), _region("vlm-region-b", crop=(0, 0, 40, 40))]
        assert len(_prepare(regions)) == 2
        _rejected(_E.PAYLOAD_LIMIT, regions, max_total_payload_bytes=10)

    def test_governed_limits_are_the_existing_vlm_limits(self):
        limits = VlmLimits()
        assert (limits.requests_per_document, limits.regions_total) == (64, 64)
        assert (limits.crop_png_bytes, limits.crop_pixels) == (4 * 1024 * 1024, 4_194_304)
        assert limits.crop_longest_edge_px == 2_048


# ---------------------------------------------------------------------------
# T22 / T23 / T24 / T25 — bounded context, no leakage
# ---------------------------------------------------------------------------


class TestContextBounding:
    def test_blind_mode_sends_no_context_even_when_dimensions_exist(self):
        (item,) = _prepare(base=_base(_dimension()))
        assert item.request.context_text == ()

    def test_t22_guided_context_is_only_linked_deterministic_text(self):
        base = _base(
            _dimension("d1", text="25 mm", ids=("t1",)),
            _dimension("d2", text="UNRELATED SECRET NOTE", ids=("other",)),
            _dimension("d3", text="PAGE TWO", ids=("t1",), page=2),
        )
        (item,) = _prepare(base=base, mode=DrawingVlmMode.GUIDED, max_context_chars=100)
        assert item.request.context_text == ("25 mm",)
        assert "UNRELATED" not in repr(item) and "PAGE TWO" not in repr(item)

    def test_guided_context_is_sorted_and_deduplicated(self):
        base = _base(
            _dimension("d1", text="30 mm"),
            _dimension("d2", text="25 mm"),
            _dimension("d3", text="25 mm"),
        )
        (item,) = _prepare(base=base, mode=DrawingVlmMode.GUIDED, max_context_chars=100)
        assert item.request.context_text == ("25 mm", "30 mm")

    def test_guided_requires_an_explicit_cap_before_any_work(self, monkeypatch):
        calls: list[str] = []
        monkeypatch.setattr(
            vlm_request, "prepare_raster_ocr_inputs", lambda *a, **k: calls.append("decode")
        )
        _rejected(_E.CONTEXT_LIMIT_REQUIRED, mode=DrawingVlmMode.GUIDED)
        assert calls == []

    def test_guided_context_over_cap_fails_closed(self):
        _rejected(
            _E.CONTEXT_TOO_LARGE,
            base=_base(_dimension(text="25 mm")),
            mode=DrawingVlmMode.GUIDED,
            max_context_chars=3,
        )

    def test_guided_context_with_control_characters_is_rejected(self):
        _rejected(
            _E.CONTEXT_INVALID,
            base=_base(_dimension(text="25\x00mm")),
            mode=DrawingVlmMode.GUIDED,
            max_context_chars=100,
        )

    def test_t23_t24_environment_and_secrets_never_reach_a_request(self, monkeypatch):
        monkeypatch.setenv("VLM_API_KEY", "sk-super-secret-token")
        monkeypatch.setenv("AUTH_TOKEN", "bearer-secret-token")
        base = _base(_dimension())
        (item,) = _prepare(base=base, mode=DrawingVlmMode.GUIDED, max_context_chars=50)
        blob = repr(item).encode() + pickle.dumps(item) + item.request.image_png
        assert b"secret" not in blob
        assert not any(
            hasattr(item.request, name) for name in ("env", "api_key", "token", "path", "source_id")
        )

    def test_the_whole_drawing_is_never_serialized_into_a_request(self):
        base = _base(_dimension("d1", text="DISTINCT-UNRELATED-TEXT", ids=("zzz",)))
        (item,) = _prepare(base=base)
        assert "DISTINCT-UNRELATED-TEXT" not in repr(item)
        assert b"DISTINCT-UNRELATED-TEXT" not in pickle.dumps(item)

    def test_config_has_no_free_form_instruction_field(self):
        fields = set(VlmPreparationConfig.__dataclass_fields__)
        assert not fields & {"prompt", "instruction", "system", "text", "extra", "context", "path"}

    def test_config_is_validated(self):
        bad_values = (
            {"prompt_contract_version": " "},
            {"max_context_chars": 0},
            {"max_context_chars": True},
        )
        for bad in bad_values:
            with pytest.raises(ValueError):
                _config(**bad)
        with pytest.raises(TypeError):
            _config(model="not-a-model")
        with pytest.raises(TypeError):
            _config(limits=object())
        with pytest.raises(ValueError):
            _config(max_total_payload_bytes=-1)


# ---------------------------------------------------------------------------
# T26 / T30 / T31 / T32 / T33 — isolation, immutability, no network
# ---------------------------------------------------------------------------


class TestIsolation:
    def test_t32_t33_preparation_does_not_touch_the_deterministic_result(self):
        base = _base(_dimension())
        before = repr(base)
        _prepare(base=base, mode=DrawingVlmMode.GUIDED, max_context_chars=50)
        assert repr(base) == before
        assert base.document.all_dimensions[0].source_location.authority is (
            DrawingExtractionAuthority.EXTRACTED
        )

    def test_preparation_executes_no_provider_parser_or_reconciliation(self, monkeypatch):
        import backend.interoperability.vlm_assist as vlm_assist
        import backend.interoperability.vlm_reconciliation as reconciliation
        import backend.interoperability.vlm_response as response

        def _boom(*args, **kwargs):
            raise AssertionError("must not run during request preparation")

        monkeypatch.setattr(vlm_assist.AiAssistedDrawingExtractor, "extract_candidates", _boom)
        monkeypatch.setattr(response, "parse_vlm_response", _boom)
        monkeypatch.setattr(reconciliation, "reconcile_advisory_evidence", _boom)
        assert len(_prepare()) == 1

    def test_preparation_does_not_run_ocr_or_gdt(self, monkeypatch):
        import backend.interoperability.gdt_drawing as gdt_drawing

        def _boom(*args, **kwargs):
            raise AssertionError("must not run during request preparation")

        monkeypatch.setattr(ocr_drawing, "extract_ocr_from_pdf", _boom)
        monkeypatch.setattr(gdt_drawing, "recognize_feature_control_frames", _boom)
        monkeypatch.setattr(ocr_drawing.pytesseract, "image_to_data", _boom)
        assert len(_prepare()) == 1

    @pytest.mark.parametrize(
        "module", [pdf_drawing, ocr_drawing, raster_drawing], ids=lambda m: m.__name__
    )
    def test_t30_t31_deterministic_modules_never_reference_request_preparation(self, module):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for name in ("vlm_request", "prepare_vlm_requests", "vlm_assist"):
            assert name not in source

    def test_t30_vector_parser_cannot_reach_request_preparation(self):
        import inspect

        source = inspect.getsource(pdf_drawing.VectorPdfDrawingParser).lower()
        assert "vlm" not in source and "prepare_vlm" not in source

    def test_authority_constants_are_unchanged(self):
        import backend.interoperability.vlm_assist as vlm_assist

        assert vlm_assist.AI_DEFAULT_AUTHORITY is DrawingExtractionAuthority.ADVISORY
        assert vlm_assist.AUTO_PROMOTION_ALLOWED is False
        assert vlm_assist.DETERMINISTIC_EVIDENCE_OVERWRITE_ALLOWED is False

    def test_t26_module_has_no_network_sdk_env_clock_random_or_filesystem_imports(self):
        path = Path(vlm_request.__file__)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        forbidden = re.compile(
            r"^(socket|ssl|http|urllib|requests|httpx|aiohttp|openai|anthropic|google|azure|"
            r"boto3|ollama|transformers|huggingface_hub|random|secrets|uuid|os|subprocess|"
            r"pathlib|datetime|time|tempfile|shutil|glob)(\.|$)"
        )
        assert not [name for name in imported if forbidden.match(name)]
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        assert not names & {"environ", "getenv", "open", "socket", "urlopen", "read_bytes"}

    def test_error_carries_only_a_stable_code(self):
        error = VlmPreparationError(_E.NO_REGIONS)
        assert str(error) == "NO_REGIONS" and repr(error) == "VlmPreparationError(NO_REGIONS)"
        assert pickle.loads(pickle.dumps(error)).code is _E.NO_REGIONS
        with pytest.raises(TypeError):
            VlmPreparationError("free text")  # type: ignore[arg-type]

    def test_argument_types_are_validated(self):
        with pytest.raises(TypeError):
            prepare_vlm_requests("x", _PDF, [_region()], config=_config())  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            prepare_vlm_requests(_base(), _PDF, [_region()], config=object())  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            prepare_vlm_requests(_base(), _PDF, ["x"], config=_config())  # type: ignore[list-item]

    def test_prepared_request_validates_its_parts(self):
        (item,) = _prepare()
        with pytest.raises(TypeError):
            PreparedVlmRequest("x", item.region, item.payload_sha256, "s")  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            PreparedVlmRequest(item.request, "x", item.payload_sha256, "s")  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            PreparedVlmRequest(item.request, item.region, item.payload_sha256, " ")


def test_parser_identity_import_is_only_for_fixtures():
    # Guard against accidentally relying on a fixture-only identity in production code.
    assert DrawingParserIdentity("a", "1").parser_id == "a"
