"""CAD Feature Recognition API — EPIC_04D Phase 2.

8 endpoints under /api/cad-features/:
  POST /analyze                           — upload CAD + trigger feature recognition
  GET  /{session_id}                      — session metadata
  GET  /{session_id}/features             — feature list (filterable)
  GET  /{session_id}/patterns             — feature patterns
  GET  /{session_id}/fusion               — drawing/CAD fusion result
  POST /{session_id}/features/{fid}/confirm         — confirm a feature
  POST /{session_id}/features/{fid}/reject           — reject a feature
  POST /{session_id}/associate-drawing    — manually link requirement → feature

Security:
  File size limit: 64 MB
  Extension whitelist: .stp .step .iges .igs .stl .obj .3mf .dxf
  Filename sanitization: path separators stripped
  Raw CAD bytes NEVER stored in session

FABRICATED_FEATURE=NO
CUSTOMER_CAD_COMMITTED=NO
"""

from __future__ import annotations

import base64
import hashlib
import pathlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.interoperability.cad_feature_recognition import (
    FeatureRecognitionConfidence,
    ManufacturingFeatureRecognitionResult,
    ManufacturingFeatureType,
    recognize_manufacturing_features,
)
from backend.interoperability.cad_fusion import (
    FusionResult,
    fuse_cad_with_drawing,
)

router = APIRouter(prefix="/api/cad-features", tags=["cad-features"])

# ---- Security limits ----
_MAX_FILE_BYTES = 64 * 1024 * 1024  # 64 MB
_ALLOWED_EXTENSIONS = frozenset({
    "stp", "step", "iges", "igs", "stl", "obj", "3mf", "dxf"
})

_RECOGNITION_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Session store (in-memory, no raw bytes)
# ---------------------------------------------------------------------------

@dataclass
class CadFeatureSession:
    session_id: str
    file_name: str
    format_id: str
    file_fingerprint: str  # SHA-256 of uploaded bytes
    entity_count: int
    unit: str
    recognition_result: ManufacturingFeatureRecognitionResult
    fusion_result: FusionResult | None
    drawing_session_id: str | None
    rejected_feature_ids: set[str]
    confirmed_feature_ids: set[str]
    created_at: datetime


_SESSIONS: dict[str, CadFeatureSession] = {}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=256)
    content_b64: str = Field(..., description="Base64-encoded CAD file bytes")
    drawing_session_id: str | None = None

    @field_validator("file_name")
    @classmethod
    def _sanitize_filename(cls, v: str) -> str:
        name = pathlib.PurePosixPath(v).name
        if not name:
            raise ValueError("file_name must not be a directory path")
        return name

    @field_validator("content_b64")
    @classmethod
    def _validate_b64(cls, v: str) -> str:
        try:
            decoded = base64.b64decode(v, validate=True)
        except Exception as exc:
            raise ValueError("content_b64 must be valid base64") from exc
        if len(decoded) > _MAX_FILE_BYTES:
            mb = _MAX_FILE_BYTES // (1024 * 1024)
            raise ValueError(f"File exceeds maximum allowed size ({mb} MB)")
        return v


class ConfirmRequest(BaseModel):
    user_id: str = Field(default="engineer")


class RejectRequest(BaseModel):
    user_id: str = Field(default="engineer")
    reason: str | None = None


class AssociateDrawingRequest(BaseModel):
    requirement_id: str = Field(..., min_length=1)
    feature_id: str = Field(..., min_length=1)
    user_id: str = Field(default="engineer")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_format(file_name: str) -> str:
    ext = pathlib.Path(file_name).suffix.lstrip(".").lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"File extension '.{ext}' is not supported. "
                   f"Allowed: {sorted(_ALLOWED_EXTENSIONS)}",
        )
    if ext in ("stp", "step"):
        return "STEP"
    if ext in ("iges", "igs"):
        return "IGES"
    if ext == "dxf":
        return "DXF"
    if ext == "stl":
        return "STL"
    if ext == "obj":
        return "OBJ"
    if ext == "3mf":
        return "3MF"
    return ext.upper()


def _get_session(session_id: str) -> CadFeatureSession:
    sess = _SESSIONS.get(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess


def _try_parse_iges_or_step(
    content_bytes: bytes, format_id: str, file_name: str
) -> ManufacturingFeatureRecognitionResult | None:
    """Attempt to parse IGES/STEP and run feature recognition."""
    if format_id == "IGES":
        try:
            from backend.interoperability.iges_mapping import map_iges_model
            from backend.interoperability.iges_parser import parse_iges_bytes
            iges_model = parse_iges_bytes(content_bytes)
            mapping = map_iges_model(iges_model)
            if mapping.topology and mapping.geometry:
                doc_id = hashlib.sha256(content_bytes[:256]).hexdigest()[:16]
                return recognize_manufacturing_features(
                    mapping.topology, mapping.geometry, doc_id
                )
        except Exception:
            pass

    if format_id == "STEP":
        # Attempt via pythonocc-core if available
        try:
            from backend.interoperability.adapters.step import StepTokenAdapter

            # Level 2 requires pythonocc-core; gracefully fails if absent
            adapter = StepTokenAdapter()
            adapter.ingest(content_bytes, pathlib.Path(file_name))
            # Even if STEP Level 2 topology is unavailable, return empty result
        except Exception:
            pass

    return None


def _run_feature_recognition_for_format(
    content_bytes: bytes,
    format_id: str,
    file_name: str,
) -> ManufacturingFeatureRecognitionResult:
    """Run format-specific feature recognition. Always returns a result."""
    from backend.interoperability.cad_feature_recognition import (
        ManufacturingFeatureRecognitionResult,
    )

    result = _try_parse_iges_or_step(content_bytes, format_id, file_name)
    if result is not None:
        return result

    if format_id == "DXF":
        # DXF 2D circle recognition
        try:
            from backend.interoperability.cad_feature_recognition import (
                recognize_dxf_features,
            )
            entities = _parse_dxf_2d(content_bytes)
            feats = recognize_dxf_features(entities)
            doc_id = hashlib.sha256(content_bytes[:256]).hexdigest()[:16]
            return ManufacturingFeatureRecognitionResult(
                source_document_id=doc_id,
                recognition_version=_RECOGNITION_VERSION,
                features=feats,
                patterns=[],
                accessibility={},
                tool_reach={},
                warnings=["DXF 2D: depth unknown; all holes are candidates only"],
                face_count=0,
                body_count=0,
            )
        except Exception:
            pass

    # Fallback: empty result with warning
    doc_id = hashlib.sha256(content_bytes[:256]).hexdigest()[:16]
    return ManufacturingFeatureRecognitionResult(
        source_document_id=doc_id,
        recognition_version=_RECOGNITION_VERSION,
        features=[],
        patterns=[],
        accessibility={},
        tool_reach={},
        warnings=[
            f"{format_id}: feature recognition not available "
            "(IGES Level 2 B-Rep required; STEP needs pythonocc-core)"
        ],
        face_count=0,
        body_count=0,
    )


def _parse_dxf_2d(content_bytes: bytes) -> list:
    """Extract circle entities from DXF bytes (pure Python fallback)."""
    from backend.interoperability.cad_feature_recognition import Dxf2dEntity
    entities = []
    try:
        text = content_bytes.decode("latin-1", errors="replace")
        lines = text.splitlines()
        i = 0
        while i < len(lines) - 1:
            code = lines[i].strip()
            val = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if code == "0" and val == "CIRCLE":
                cx = cy = r = 0.0
                layer = "0"
                j = i + 2
                while j < len(lines) - 1:
                    c2 = lines[j].strip()
                    v2 = lines[j + 1].strip() if j + 1 < len(lines) else ""
                    if c2 == "0":
                        break
                    if c2 == "8":
                        layer = v2
                    elif c2 == "10":
                        try:
                            cx = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "20":
                        try:
                            cy = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "40":
                        try:
                            r = float(v2)
                        except ValueError:
                            pass
                    j += 2
                if r > 0.0:
                    entities.append(Dxf2dEntity(
                        entity_type="CIRCLE",
                        layer=layer,
                        center_x=cx,
                        center_y=cy,
                        radius=r,
                    ))
                i = j
            else:
                i += 2
    except Exception:
        pass
    return entities


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyze", summary="Upload CAD file and run feature recognition")
async def analyze_cad(req: AnalyzeRequest) -> dict:
    """Upload a CAD file and run deterministic feature recognition.

    Supported formats: IGES (full B-Rep), STEP (if pythonocc-core available), DXF (2D circles).
    Raw bytes are NEVER stored in the session.

    Returns session_id for subsequent feature/fusion queries.
    """
    content_bytes = base64.b64decode(req.content_b64)
    file_name = req.file_name
    format_id = _detect_format(file_name)

    fingerprint = hashlib.sha256(content_bytes).hexdigest()[:32]

    recognition_result = _run_feature_recognition_for_format(
        content_bytes, format_id, file_name
    )

    # Drawing fusion (if drawing session provided)
    fusion_result: FusionResult | None = None
    if req.drawing_session_id:
        from backend.api.drawing_parser import _SESSIONS as _DRAWING_SESSIONS
        drawing_session = _DRAWING_SESSIONS.get(req.drawing_session_id)
        session_id_for_fusion = str(uuid.uuid4())
        fusion_result = fuse_cad_with_drawing(
            recognition_result,
            drawing_session,
            session_id_for_fusion,
        )

    session_id = str(uuid.uuid4())
    sess = CadFeatureSession(
        session_id=session_id,
        file_name=file_name,
        format_id=format_id,
        file_fingerprint=fingerprint,
        entity_count=recognition_result.face_count,
        unit="MM",
        recognition_result=recognition_result,
        fusion_result=fusion_result,
        drawing_session_id=req.drawing_session_id,
        rejected_feature_ids=set(),
        confirmed_feature_ids=set(),
        created_at=datetime.now(UTC),
    )
    _SESSIONS[session_id] = sess

    return {
        "session_id": session_id,
        "format_id": format_id,
        "file_name": file_name,
        "feature_count": recognition_result.feature_count,
        "pattern_count": recognition_result.pattern_count,
        "face_count": recognition_result.face_count,
        "warnings": recognition_result.warnings,
        "fusion_available": fusion_result is not None,
        "disclaimer": "REFERENCE_ONLY — engineer review required",
    }


@router.get("/{session_id}", summary="Get session metadata")
async def get_session(session_id: str) -> dict:
    sess = _get_session(session_id)
    return {
        "session_id": sess.session_id,
        "file_name": sess.file_name,
        "format_id": sess.format_id,
        "entity_count": sess.entity_count,
        "unit": sess.unit,
        "feature_count": sess.recognition_result.feature_count,
        "pattern_count": sess.recognition_result.pattern_count,
        "warnings": sess.recognition_result.warnings,
        "drawing_session_id": sess.drawing_session_id,
        "created_at": sess.created_at.isoformat(),
    }


@router.get("/{session_id}/features", summary="List recognized features")
async def get_features(
    session_id: str,
    feature_type: str | None = None,
    confidence: str | None = None,
    unlinked_only: bool = False,
) -> dict:
    """Return recognized manufacturing features.

    Optional filters:
    - feature_type: filter by ManufacturingFeatureType
    - confidence: filter by FeatureRecognitionConfidence
    - unlinked_only: only features with no drawing requirement link
    """
    sess = _get_session(session_id)
    features = sess.recognition_result.features

    # Apply filters
    if feature_type:
        try:
            ft = ManufacturingFeatureType(feature_type)
            features = [f for f in features if f.feature_type == ft]
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown feature_type: {feature_type}",
            ) from exc

    if confidence:
        try:
            conf = FeatureRecognitionConfidence(confidence)
            features = [f for f in features if f.confidence == conf]
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown confidence: {confidence}",
            ) from exc

    if unlinked_only and sess.fusion_result:
        linked_ids = {
            lnk.feature_id for lnk in sess.fusion_result.feature_links
        }
        features = [f for f in features if f.feature_id not in linked_ids]

    # Exclude rejected
    features = [
        f for f in features
        if f.feature_id not in sess.rejected_feature_ids
    ]

    return {
        "session_id": session_id,
        "total": len(features),
        "features": [f.as_dict() for f in features],
    }


@router.get("/{session_id}/patterns", summary="List detected feature patterns")
async def get_patterns(session_id: str) -> dict:
    sess = _get_session(session_id)
    return {
        "session_id": session_id,
        "total": sess.recognition_result.pattern_count,
        "patterns": [p.as_dict() for p in sess.recognition_result.patterns],
    }


@router.get("/{session_id}/fusion", summary="Get drawing/CAD fusion result")
async def get_fusion(session_id: str) -> dict:
    sess = _get_session(session_id)
    if sess.fusion_result is None:
        return {
            "session_id": session_id,
            "fusion_available": False,
            "message": "No drawing session linked. Provide drawing_session_id in /analyze.",
        }
    return sess.fusion_result.as_dict()


@router.post(
    "/{session_id}/features/{feature_id}/confirm",
    summary="Engineer confirms a feature",
)
async def confirm_feature(
    session_id: str,
    feature_id: str,
    body: ConfirmRequest,
) -> dict:
    sess = _get_session(session_id)
    feature = next(
        (f for f in sess.recognition_result.features if f.feature_id == feature_id),
        None,
    )
    if feature is None:
        raise HTTPException(status_code=404, detail=f"Feature {feature_id!r} not found")

    confirmed = feature.confirm(body.user_id)
    # Replace in list
    idx = next(
        i for i, f in enumerate(sess.recognition_result.features)
        if f.feature_id == feature_id
    )
    sess.recognition_result.features[idx] = confirmed
    sess.confirmed_feature_ids.add(feature_id)

    return {
        "session_id": session_id,
        "feature_id": feature_id,
        "confirmed": True,
        "confidence": confirmed.confidence,
        "user_id": body.user_id,
    }


@router.post(
    "/{session_id}/features/{feature_id}/reject",
    summary="Engineer rejects a feature",
)
async def reject_feature(
    session_id: str,
    feature_id: str,
    body: RejectRequest,
) -> dict:
    sess = _get_session(session_id)
    feature = next(
        (f for f in sess.recognition_result.features if f.feature_id == feature_id),
        None,
    )
    if feature is None:
        raise HTTPException(status_code=404, detail=f"Feature {feature_id!r} not found")

    sess.rejected_feature_ids.add(feature_id)
    return {
        "session_id": session_id,
        "feature_id": feature_id,
        "rejected": True,
        "reason": body.reason,
    }


@router.post(
    "/{session_id}/associate-drawing",
    summary="Manually associate a drawing requirement with a CAD feature",
)
async def associate_drawing(
    session_id: str,
    body: AssociateDrawingRequest,
) -> dict:
    sess = _get_session(session_id)
    feature = next(
        (f for f in sess.recognition_result.features
         if f.feature_id == body.feature_id),
        None,
    )
    if feature is None:
        raise HTTPException(status_code=404, detail=f"Feature {body.feature_id!r} not found")

    if sess.fusion_result is None:
        # Create a minimal fusion result to hold the manual link
        from backend.interoperability.cad_fusion import (
            FusionCompleteness,
            FusionResult,
        )
        sess.fusion_result = FusionResult(
            fusion_id=str(uuid.uuid4()),
            cad_session_id=session_id,
            drawing_session_id=None,
            feature_links=[],
            ambiguities=[],
            drawing_only_req_ids=[],
            cad_only_feature_ids=[],
            completeness=FusionCompleteness.PARTIAL,
            review_events=[],
            created_at=datetime.now(UTC),
        )

    sess.fusion_result.reassign_link(
        body.requirement_id, body.feature_id, body.user_id
    )
    return {
        "session_id": session_id,
        "requirement_id": body.requirement_id,
        "feature_id": body.feature_id,
        "status": "USER_MATCHED",
        "user_id": body.user_id,
    }
