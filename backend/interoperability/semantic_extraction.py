"""Unified drawing semantic extraction pipeline.

Orchestrates the full extraction flow:
  RAW_EXTRACTION → TOKEN_NORMALIZATION → SYMBOL_DETECTION → SEMANTIC_PARSE
  → GRAPHICAL_ASSOCIATION → FEATURE_ASSOCIATION → CONFIDENCE_ASSIGNMENT
  → AMBIGUITY_DETECTION → ENGINEER_REVIEW

FABRICATED_DIMENSION=NO
FABRICATED_TOLERANCE=NO
FABRICATED_FIT=NO
FABRICATED_GDT=NO
FABRICATED_DATUM=NO
FABRICATED_SURFACE_FINISH=NO
FABRICATED_THREAD=NO
FABRICATED_FEATURE_ASSOCIATION=NO
UNCERTAIN_EXTRACTION_AUTO_APPROVED=NO
LLM_ALLOWED_TO_CREATE_UNOBSERVED_DIMENSION=NO
LLM_ALLOWED_TO_CREATE_UNOBSERVED_GDT=NO
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum, unique
from typing import Any

from backend.interoperability.association import AssociationState, FeatureType
from backend.interoperability.fit_drawing import parse_fit_token
from backend.interoperability.surface_finish_drawing import parse_surface_finish_token
from backend.interoperability.thread_drawing import parse_thread_token

# ---------------------------------------------------------------------------
# Confidence model
# ---------------------------------------------------------------------------

@unique
class ParserConfidence(StrEnum):
    EXACT_VECTOR_TEXT = "EXACT_VECTOR_TEXT"       # Clean vector text, exact match
    VECTOR_PATTERN_PARSED = "VECTOR_PATTERN_PARSED"  # Regex-matched from vector
    HIGH_CONFIDENCE_OCR = "HIGH_CONFIDENCE_OCR"   # OCR conf ≥ 0.90
    LOW_CONFIDENCE_OCR = "LOW_CONFIDENCE_OCR"     # OCR conf in [0.80, 0.90)
    SYMBOL_DETECTED = "SYMBOL_DETECTED"           # Glyph/symbol from pixel pattern
    GEOMETRY_ASSOCIATED = "GEOMETRY_ASSOCIATED"   # Source: geometry inference
    AMBIGUOUS = "AMBIGUOUS"                       # Multiple interpretations
    USER_CONFIRMED = "USER_CONFIRMED"             # Engineer explicitly confirmed


_CONFIDENCE_VALUES: dict[ParserConfidence, Decimal] = {
    ParserConfidence.EXACT_VECTOR_TEXT: Decimal("0.99"),
    ParserConfidence.VECTOR_PATTERN_PARSED: Decimal("0.92"),
    ParserConfidence.HIGH_CONFIDENCE_OCR: Decimal("0.88"),
    ParserConfidence.LOW_CONFIDENCE_OCR: Decimal("0.72"),
    ParserConfidence.SYMBOL_DETECTED: Decimal("0.80"),
    ParserConfidence.GEOMETRY_ASSOCIATED: Decimal("0.75"),
    ParserConfidence.AMBIGUOUS: Decimal("0.50"),
    ParserConfidence.USER_CONFIRMED: Decimal("1.00"),
}

REVIEW_REQUIRED_THRESHOLD = Decimal("0.85")


def confidence_value(method: ParserConfidence) -> Decimal:
    return _CONFIDENCE_VALUES[method]


def requires_review(confidence: Decimal) -> bool:
    return confidence < REVIEW_REQUIRED_THRESHOLD


# ---------------------------------------------------------------------------
# Ambiguity model
# ---------------------------------------------------------------------------

@unique
class AmbiguityKind(StrEnum):
    MULTIPLE_LEADER_CANDIDATES = "MULTIPLE_LEADER_CANDIDATES"
    AMBIGUOUS_DECIMAL = "AMBIGUOUS_DECIMAL"
    AMBIGUOUS_DATUM = "AMBIGUOUS_DATUM"
    AMBIGUOUS_FCF = "AMBIGUOUS_FCF"
    BROKEN_SYMBOL = "BROKEN_SYMBOL"
    LOW_OCR_CONFIDENCE = "LOW_OCR_CONFIDENCE"
    MULTIPLE_FEATURE_CANDIDATES = "MULTIPLE_FEATURE_CANDIDATES"
    UNKNOWN_UNIT = "UNKNOWN_UNIT"
    UNKNOWN_STANDARD_CONTEXT = "UNKNOWN_STANDARD_CONTEXT"


@dataclass(frozen=True)
class DetectionAmbiguity:
    kind: AmbiguityKind
    detection_id: str
    description: str
    candidate_values: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Normalized detection model
# ---------------------------------------------------------------------------

@unique
class DetectionSourceType(StrEnum):
    VECTOR_PDF = "VECTOR_PDF"
    OCR = "OCR"
    DXF = "DXF"
    STEP = "STEP"
    IGES = "IGES"
    MANUAL = "MANUAL"


@unique
class NormalizedDetectionType(StrEnum):
    DIMENSION = "DIMENSION"
    TOLERANCE = "TOLERANCE"
    FIT = "FIT"
    THREAD = "THREAD"
    SURFACE_FINISH = "SURFACE_FINISH"
    GDT_FCF = "GDT_FCF"
    DATUM = "DATUM"
    NOTE = "NOTE"
    TITLE_FIELD = "TITLE_FIELD"
    GENERAL_TOLERANCE = "GENERAL_TOLERANCE"
    UNKNOWN = "UNKNOWN"


@unique
class ReviewState(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    EDITED = "EDITED"
    REJECTED = "REJECTED"


@dataclass
class NormalizedDetection:
    """Unified detection record from any drawing source."""

    detection_id: str
    page: int | None
    source_type: DetectionSourceType
    bounding_box: dict[str, Any] | None       # {"x", "y", "w", "h"} in pts
    raw_text: str | None
    raw_symbol: str | None
    normalized_type: NormalizedDetectionType
    normalized_value: str | None              # Human-readable value string
    unit: str | None
    confidence: Decimal
    confidence_method: ParserConfidence
    parser_method: str
    association_state: AssociationState = AssociationState.UNRESOLVED
    association_feature_id: str | None = None
    association_feature_type: FeatureType = FeatureType.UNKNOWN
    review_state: ReviewState = ReviewState.PENDING
    ambiguities: list[DetectionAmbiguity] = field(default_factory=list)
    subtype: str | None = None                # e.g. "DIAMETRAL", "SYMMETRIC"

    @property
    def review_required(self) -> bool:
        return (
            self.review_state == ReviewState.PENDING
            and (requires_review(self.confidence) or bool(self.ambiguities))
        )


# ---------------------------------------------------------------------------
# General tolerance model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GeneralToleranceSpec:
    standard: str | None              # e.g. "ISO 2768-1 medium", "±0.1"
    linear_tolerance_mm: Decimal | None
    angular_tolerance_deg: Decimal | None
    source_field: str | None          # "title_block" or "note"
    raw_text: str | None


# ---------------------------------------------------------------------------
# Unit detection
# ---------------------------------------------------------------------------

_UNIT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bALL\s*DIMENSIONS?\s*IN\s*MM\b", re.IGNORECASE), "mm"),
    (re.compile(r"\bDIMENSIONS?\s*IN\s*MM\b", re.IGNORECASE), "mm"),
    (re.compile(r"\bALL\s*DIMENSIONS?\s*IN\s*INCH(?:ES)?\b", re.IGNORECASE), "inch"),
    (re.compile(r"\bDIMENSIONS?\s*IN\s*INCH(?:ES)?\b", re.IGNORECASE), "inch"),
    (re.compile(r"\bUNLESS\s*OTHERWISE\s*STATED.*\b(MM|MILLIMETRE)\b", re.IGNORECASE), "mm"),
]

_STANDARD_UNIT_MAP = {
    "ISO": "mm",
    "DIN": "mm",
    "BS": "mm",
    "JIS": "mm",
    "ANSI": "inch",
    "ASME": "inch",
    "INCH": "inch",
    "MM": "mm",
}


def detect_drawing_unit(
    title_block_unit: str | None,
    notes: list[str],
    drawing_standard: str | None,
) -> str | None:
    """Detect drawing unit from title block, notes, or standard.

    Returns "mm", "inch", or None (UNKNOWN — never silently assumed).
    """
    if title_block_unit:
        u = title_block_unit.strip().upper()
        if u in ("MM", "MILLIMETRE", "MILLIMETER"):
            return "mm"
        if u in ("INCH", "IN", "INCHES", "\""):
            return "inch"

    for note_text in notes:
        for pattern, unit in _UNIT_PATTERNS:
            if pattern.search(note_text):
                return unit

    if drawing_standard:
        std_upper = drawing_standard.strip().upper()
        for key, unit in _STANDARD_UNIT_MAP.items():
            if key in std_upper:
                return unit

    return None  # UNIT_STATUS=UNKNOWN; never silently assume mm


# ---------------------------------------------------------------------------
# General tolerance extraction
# ---------------------------------------------------------------------------

_ISO2768_RE = re.compile(
    r"ISO\s*2768\s*[-–]?\s*(\d+)?\s*([mfcvk])?",
    re.IGNORECASE,
)
_LINEAR_TOL_RE = re.compile(
    r"±\s*(\d+(?:[.,]\d+)?)\s*(mm)?",
    re.IGNORECASE,
)


def extract_general_tolerance(texts: list[str]) -> GeneralToleranceSpec | None:
    """Extract general tolerance from title block fields or note texts."""
    for text in texts:
        m = _ISO2768_RE.search(text)
        if m:
            class_char = m.group(2) or ""
            _class_tol: dict[str, Decimal] = {
                "f": Decimal("0.05"), "m": Decimal("0.1"),
                "c": Decimal("0.2"), "v": Decimal("0.5"),
            }
            lin = _class_tol.get(class_char.lower()) if class_char else None
            return GeneralToleranceSpec(
                standard=f"ISO 2768 {class_char}".strip(),
                linear_tolerance_mm=lin,
                angular_tolerance_deg=None,
                source_field="note",
                raw_text=text.strip(),
            )
        m2 = _LINEAR_TOL_RE.search(text)
        if m2:
            try:
                val = Decimal(m2.group(1).replace(",", "."))
            except Exception:
                continue
            return GeneralToleranceSpec(
                standard=None,
                linear_tolerance_mm=val,
                angular_tolerance_deg=None,
                source_field="note",
                raw_text=text.strip(),
            )
    return None


# ---------------------------------------------------------------------------
# OCR runtime configuration
# ---------------------------------------------------------------------------

def resolve_tesseract_command() -> str | None:
    """Resolve Tesseract binary path from environment or PATH.

    Returns command string if available, None if unavailable.
    HARDCODED_TESSERACT_PATH=NO — only env var or PATH discovery used.
    """
    env_cmd = os.environ.get("TESSERACT_CMD", "").strip()
    if env_cmd:
        return env_cmd

    import shutil
    found = shutil.which("tesseract")
    return found  # None if not on PATH


def ocr_available() -> bool:
    return resolve_tesseract_command() is not None


# ---------------------------------------------------------------------------
# Raster preprocessing
# ---------------------------------------------------------------------------

def preprocess_raster_image(
    image_bytes: bytes,
    *,
    deskew: bool = True,
    denoise: bool = True,
    adaptive_threshold: bool = False,
) -> bytes:
    """Apply bounded preprocessing to a raster image for OCR.

    Returns preprocessed grayscale image bytes (PNG).
    Does not destroy fine drawing symbols.

    Requires Pillow. Does not require any additional packages.
    """
    try:
        import io

        from PIL import Image, ImageFilter, ImageOps
    except ImportError:
        return image_bytes

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Convert to grayscale
            gray = img.convert("L")

            # Contrast normalization (CLAHE-like via autocontrast)
            enhanced = ImageOps.autocontrast(gray, cutoff=1)

            # Denoise: mild median filter
            if denoise:
                enhanced = enhanced.filter(ImageFilter.MedianFilter(size=3))

            # Adaptive threshold: convert to near-binary for OCR
            if adaptive_threshold:
                # Simple global threshold; true adaptive requires numpy
                threshold = 128
                enhanced = enhanced.point(lambda x: 255 if x > threshold else 0)

            # Deskew: detect dominant angle using horizontal projection
            # Simple heuristic — rotate by up to ±5 degrees if needed
            if deskew:
                enhanced = _deskew_image(enhanced)

            buf = io.BytesIO()
            enhanced.save(buf, format="PNG")
            return buf.getvalue()
    except Exception:
        return image_bytes


def _deskew_image(img: Any) -> Any:
    """Minimal deskew using horizontal projection analysis."""
    try:
        # Only attempt deskew if image is wide enough
        w, h = img.size
        if w < 100 or h < 100:
            return img

        # Simple angle detection: try ±3 degrees and pick best
        best_img = img
        best_score = _projection_score(img)
        for angle_tenths in range(-30, 31, 5):
            angle = angle_tenths / 10.0
            if angle == 0.0:
                continue
            rotated = img.rotate(angle, expand=False, fillcolor=255)
            score = _projection_score(rotated)
            if score > best_score:
                best_score = score
                best_img = rotated
        return best_img
    except Exception:
        return img


def _projection_score(img: Any) -> float:
    """Horizontal projection score: higher when text lines are horizontal."""
    try:
        pixels = list(img.getdata())
        w, h = img.size
        rows: list[int] = []
        for y in range(h):
            row_pixels = pixels[y * w: (y + 1) * w]
            dark = sum(1 for p in row_pixels if p < 128)
            rows.append(dark)
        # Variance: higher when rows alternate between text and space
        mean = sum(rows) / len(rows) if rows else 0
        variance = sum((r - mean) ** 2 for r in rows) / max(len(rows), 1)
        return variance
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Composite FCF parser
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FcfSegment:
    """A single segment of a feature control frame."""
    characteristic: str
    tolerance_value: Decimal | None
    tolerance_unit: str | None
    diameter_zone: bool
    modifier: str | None
    datum_labels: tuple[str, ...]


@dataclass(frozen=True)
class ParsedCompositeFCF:
    """Multi-segment FCF with PLTZF (upper) and FRTZF (lower) segments."""
    upper_segment: FcfSegment    # Pattern-Locating Tolerance Zone Framework
    lower_segment: FcfSegment    # Feature-Relating Tolerance Zone Framework
    raw_text: str
    confidence: Decimal


_TOL_RE = re.compile(r"[ØøÐ]?\s*(\d+(?:[.,]\d+)?)\s*(mm|in)?", re.IGNORECASE)
_DATUM_RE = re.compile(r"\b([A-Z])(?:-([A-Z]))?\b")
_MODIFIER_RE = re.compile(r"\b(MMC|LMC|RFS)\b", re.IGNORECASE)

_CHARACTERISTICS = {
    "STRAIGHTNESS", "FLATNESS", "CIRCULARITY", "CYLINDRICITY",
    "PROFILE_OF_A_LINE", "PROFILE_OF_A_SURFACE",
    "PERPENDICULARITY", "ANGULARITY", "PARALLELISM",
    "POSITION", "CONCENTRICITY", "SYMMETRY",
    "CIRCULAR_RUNOUT", "TOTAL_RUNOUT",
}


def _parse_fcf_segment(text: str, characteristic: str | None = None) -> FcfSegment | None:
    """Parse a single FCF segment from a text band."""
    text = text.strip().upper()

    # Detect characteristic
    char = characteristic
    if char is None:
        for c in _CHARACTERISTICS:
            c_normalized = c.replace("_", " ")
            if c in text or c_normalized in text:
                char = c
                break
    if char is None:
        return None

    # Extract tolerance value
    tol_value: Decimal | None = None
    tol_unit: str | None = None
    diameter_zone = False
    m = _TOL_RE.search(text)
    if m:
        try:
            tol_value = Decimal(m.group(1).replace(",", "."))
        except Exception:
            pass
        unit_raw = m.group(2)
        tol_unit = "mm" if not unit_raw or unit_raw.lower() == "mm" else "inch"
        prefix_text = text[: text.index(m.group(0))] if m.group(0) in text else text
        diameter_zone = bool(re.search(r"[Øø]", prefix_text))

    # Extract modifier
    modifier: str | None = None
    mm = _MODIFIER_RE.search(text)
    if mm:
        modifier = mm.group(1).upper()

    # Extract datums
    datum_labels: list[str] = []
    for dm in _DATUM_RE.finditer(text):
        label = dm.group(1)
        if label not in _CHARACTERISTICS and label not in ("MM", "IN"):
            datum_labels.append(label)
            if dm.group(2):
                datum_labels.append(dm.group(2))

    return FcfSegment(
        characteristic=char,
        tolerance_value=tol_value,
        tolerance_unit=tol_unit,
        diameter_zone=diameter_zone,
        modifier=modifier,
        datum_labels=tuple(dict.fromkeys(datum_labels)),  # deduplicated, order preserved
    )


def parse_composite_fcf(
    upper_text: str,
    lower_text: str,
    characteristic: str = "POSITION",
) -> ParsedCompositeFCF | None:
    """Parse a composite FCF from two text bands (upper and lower segments)."""
    upper = _parse_fcf_segment(upper_text, characteristic)
    lower = _parse_fcf_segment(lower_text, characteristic)

    if upper is None or lower is None:
        return None

    # Validate: lower tolerance must be ≤ upper tolerance
    if (
        upper.tolerance_value is not None
        and lower.tolerance_value is not None
        and lower.tolerance_value > upper.tolerance_value
    ):
        return None  # Invalid composite FCF

    raw_combined = f"{upper_text} | {lower_text}"
    confidence = Decimal("0.85")  # Composite FCF has inherent ambiguity

    return ParsedCompositeFCF(
        upper_segment=upper,
        lower_segment=lower,
        raw_text=raw_combined,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Datum detection
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DetectedDatum:
    datum_label: str          # Single letter A-Z
    compound_label: str | None  # e.g. "A-B" for compound datums
    attachment_hint: str | None  # "leader", "symbol", "fcf_cell"
    raw_text: str
    confidence: Decimal


_DATUM_SYMBOL_RE = re.compile(
    r"\bDATUM\s+([A-Z])\b"
    r"|\bDAT\.?\s+([A-Z])\b"
    r"|\[([A-Z])\]"   # datum in square bracket annotation
    r"|\b([A-Z])\s*[-–]\s*([A-Z])\b",  # compound A-B
    re.IGNORECASE,
)


def detect_datum_from_tokens(tokens: list[str]) -> list[DetectedDatum]:
    """Detect datum labels from a list of text tokens."""
    results: list[DetectedDatum] = []
    for token in tokens:
        for m in _DATUM_SYMBOL_RE.finditer(token):
            label = (m.group(1) or m.group(2) or m.group(3) or m.group(4) or "").upper()
            compound = None
            if m.group(4) and m.group(5):
                compound = f"{m.group(4).upper()}-{m.group(5).upper()}"
            if not label:
                continue
            results.append(DetectedDatum(
                datum_label=label,
                compound_label=compound,
                attachment_hint="token",
                raw_text=token,
                confidence=Decimal("0.80"),
            ))
    return results


# ---------------------------------------------------------------------------
# Material bridge result (mirroring drawing_intelligence.material_bridge)
# ---------------------------------------------------------------------------

@unique
class MaterialMatchStatus(StrEnum):
    MATCHED = "MATCHED"
    MULTIPLE_MATCHES = "MULTIPLE_MATCHES"
    NOT_FOUND = "NOT_FOUND"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class MaterialBridgeOutcome:
    raw_text: str
    status: MaterialMatchStatus
    matched_id: str | None
    matched_designation: str | None
    confidence: Decimal


def bridge_material(raw_text: str) -> MaterialBridgeOutcome:
    """Attempt to bridge a raw material string to Material Intelligence.

    No silent fuzzy auto-approval. Unknown → NOT_FOUND.
    """
    if not raw_text or not raw_text.strip():
        return MaterialBridgeOutcome(
            raw_text=raw_text, status=MaterialMatchStatus.INSUFFICIENT_DATA,
            matched_id=None, matched_designation=None,
            confidence=Decimal("0"),
        )
    try:
        from backend.drawing_intelligence.material_bridge import MaterialBridge
        bridge = MaterialBridge()
        result = bridge.resolve(raw_text.strip())
        if result.resolved:
            return MaterialBridgeOutcome(
                raw_text=raw_text,
                status=MaterialMatchStatus.MATCHED,
                matched_id=result.matched_material_id,
                matched_designation=result.matched_designation,
                confidence=Decimal("0.9") if result.confidence == "EXACT" else Decimal("0.7"),
            )
        return MaterialBridgeOutcome(
            raw_text=raw_text, status=MaterialMatchStatus.NOT_FOUND,
            matched_id=None, matched_designation=None,
            confidence=Decimal("0"),
        )
    except Exception:
        return MaterialBridgeOutcome(
            raw_text=raw_text, status=MaterialMatchStatus.NOT_FOUND,
            matched_id=None, matched_designation=None,
            confidence=Decimal("0"),
        )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

@dataclass
class ExtractionSession:
    """Result of the semantic extraction pipeline for one drawing."""

    session_id: str
    source_id: str
    source_format: str
    detections: list[NormalizedDetection] = field(default_factory=list)
    general_tolerance: GeneralToleranceSpec | None = None
    detected_unit: str | None = None        # "mm", "inch", or None (UNKNOWN)
    material_outcome: MaterialBridgeOutcome | None = None
    ambiguities: list[DetectionAmbiguity] = field(default_factory=list)
    ocr_available: bool = False
    extraction_warnings: list[str] = field(default_factory=list)

    @property
    def review_required_count(self) -> int:
        return sum(1 for d in self.detections if d.review_required)

    @property
    def confirmed_count(self) -> int:
        return sum(1 for d in self.detections if d.review_state == ReviewState.CONFIRMED)


def new_session_id() -> str:
    return f"ses-{uuid.uuid4().hex[:16]}"


def new_detection_id() -> str:
    return f"det-{uuid.uuid4().hex[:12]}"


def make_detection(
    normalized_type: NormalizedDetectionType,
    raw_text: str | None,
    normalized_value: str | None,
    unit: str | None,
    confidence_method: ParserConfidence,
    source_type: DetectionSourceType,
    page: int | None = None,
    subtype: str | None = None,
    bounding_box: dict[str, Any] | None = None,
) -> NormalizedDetection:
    """Factory for NormalizedDetection with computed review_required."""
    conf = confidence_value(confidence_method)
    detection_id = new_detection_id()
    ambiguities: list[DetectionAmbiguity] = []

    if confidence_method == ParserConfidence.LOW_CONFIDENCE_OCR:
        ambiguities.append(DetectionAmbiguity(
            kind=AmbiguityKind.LOW_OCR_CONFIDENCE,
            detection_id=detection_id,
            description="OCR confidence below 0.90 threshold",
        ))

    return NormalizedDetection(
        detection_id=detection_id,
        page=page,
        source_type=source_type,
        bounding_box=bounding_box,
        raw_text=raw_text,
        raw_symbol=None,
        normalized_type=normalized_type,
        normalized_value=normalized_value,
        unit=unit,
        confidence=conf,
        confidence_method=confidence_method,
        parser_method=confidence_method.value,
        ambiguities=ambiguities,
        subtype=subtype,
    )


def run_token_extraction(
    tokens: list[str],
    source_type: DetectionSourceType = DetectionSourceType.VECTOR_PDF,
    page: int | None = None,
) -> list[NormalizedDetection]:
    """Run the semantic parse stage over a list of text tokens.

    Attempts fit, thread, surface finish, note classification on each token.
    Returns NormalizedDetection list; all start at PENDING review state.
    """
    results: list[NormalizedDetection] = []
    confidence_method = (
        ParserConfidence.EXACT_VECTOR_TEXT
        if source_type == DetectionSourceType.VECTOR_PDF
        else ParserConfidence.HIGH_CONFIDENCE_OCR
    )

    for token in tokens:
        if not token or not token.strip():
            continue

        # Surface finish
        sf = parse_surface_finish_token(token)
        if sf is not None:
            value_str = (
                f"{sf.parameter.value} {sf.value} {sf.unit}"
                if sf.value is not None
                else sf.parameter.value
            )
            results.append(make_detection(
                NormalizedDetectionType.SURFACE_FINISH,
                raw_text=token,
                normalized_value=value_str,
                unit=sf.unit,
                confidence_method=confidence_method,
                source_type=source_type,
                page=page,
            ))
            continue

        # Thread
        tc = parse_thread_token(token)
        if tc is not None:
            results.append(make_detection(
                NormalizedDetectionType.THREAD,
                raw_text=token,
                normalized_value=f"{tc.standard.value} {tc.nominal_raw}",
                unit="mm" if tc.nominal_mm is not None else None,
                confidence_method=confidence_method,
                source_type=source_type,
                page=page,
                subtype=tc.standard.value,
            ))
            continue

        # Fit
        status, fits = parse_fit_token(token)
        if fits:
            for fit in fits:
                results.append(make_detection(
                    NormalizedDetectionType.FIT,
                    raw_text=token,
                    normalized_value=fit.fit_code,
                    unit=None,
                    confidence_method=confidence_method,
                    source_type=source_type,
                    page=page,
                    subtype=fit.fit_class.value,
                ))
            continue

    return results


def create_session(
    source_id: str,
    source_format: str,
    title_block_unit: str | None = None,
    notes: list[str] | None = None,
    drawing_standard: str | None = None,
    material_raw: str | None = None,
    general_tolerance_texts: list[str] | None = None,
) -> ExtractionSession:
    """Create an ExtractionSession with detected unit, general tolerance, material."""
    session_id = new_session_id()
    note_list = notes or []

    unit = detect_drawing_unit(title_block_unit, note_list, drawing_standard)
    warnings: list[str] = []
    if unit is None:
        warnings.append("UNIT_NOT_DECLARED")

    gen_tol_texts = (general_tolerance_texts or []) + note_list
    gen_tol = extract_general_tolerance(gen_tol_texts)

    material_outcome: MaterialBridgeOutcome | None = None
    if material_raw:
        material_outcome = bridge_material(material_raw)

    return ExtractionSession(
        session_id=session_id,
        source_id=source_id,
        source_format=source_format,
        detected_unit=unit,
        general_tolerance=gen_tol,
        material_outcome=material_outcome,
        ocr_available=ocr_available(),
        extraction_warnings=warnings,
    )
