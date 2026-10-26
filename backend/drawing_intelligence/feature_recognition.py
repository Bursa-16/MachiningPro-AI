"""Rule-based Feature Recognition Engine (EPIC_04 Phase 2).

Converts DrawingRequirementSet → list[Feature] using deterministic
dimension-pattern rules. No AI inference is performed here; all features
carry DETERMINISTIC_CALCULATION provenance.

Recognition rules (in priority order):
  R-FR-001  Thread note → THREAD Feature
  R-FR-002  Diameter dimension ≤ 100 mm with depth → HOLE Feature
  R-FR-003  Width + depth dimensions with slot keyword → SLOT Feature
  R-FR-004  Width + depth + length → POCKET Feature
  R-FR-005  Circularity / cylindricity GD&T → CYLINDRICAL_SURFACE
  R-FR-006  Flatness / parallelism GD&T → PLANAR_FACE
  R-FR-007  Chamfer keyword note → CHAMFER Feature
  R-FR-008  Fillet keyword note → FILLET Feature
  R-FR-009  Groove keyword note → GROOVE Feature
  R-FR-010  Remaining diameter dimensions → CYLINDRICAL_SURFACE

FABRICATED_FEATURE=NO
UNKNOWN_REQUIREMENT_TREATED_AS_SATISFIED=NO
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from backend.domain.base import Provenance
from backend.domain.enums import FeatureType, ProvenanceType
from backend.domain.feature import Feature
from backend.domain.units import Quantity, Unit
from backend.drawing_intelligence.requirements import (
    DimensionalRequirement,
    DrawingRequirementSet,
    GdtCharacteristic,
    GDT_CYLINDRICAL_CONTEXT,
    GeometricRequirement,
    ThreadRequirement,
)

__all__ = [
    "FeatureRecognitionResult",
    "RecognizedFeature",
    "FeatureRecognitionEngine",
    "recognize_features",
]

_PROVENANCE = Provenance(source_type=ProvenanceType.DETERMINISTIC_CALCULATION)

_THREAD_RE = re.compile(
    r"(?i)(m\d+(?:[.,x×]\d+(?:[.,]\d+)?)?|unc|unf|bsp|npt|g\d+/\d+|tr\d+|acme)",
    re.IGNORECASE,
)
_SLOT_RE = re.compile(r"(?i)slot")
_POCKET_RE = re.compile(r"(?i)pocket")
_CHAMFER_RE = re.compile(r"(?i)chamf(?:er)?")
_FILLET_RE = re.compile(r"(?i)fillet|radius")
_GROOVE_RE = re.compile(r"(?i)groov(?:e)?")
_BORE_RE = re.compile(r"(?i)bore|boring")


@dataclass(frozen=True, slots=True)
class RecognizedFeature:
    """Lightweight wrapper associating a Feature with its source requirement IDs."""

    feature: Feature
    source_req_ids: tuple[str, ...]
    recognition_rule: str


@dataclass(frozen=True, slots=True)
class FeatureRecognitionResult:
    """Output of the Feature Recognition Engine for one DrawingRequirementSet."""

    source_id: str
    features: tuple[RecognizedFeature, ...]
    unrecognized_req_ids: tuple[str, ...]
    recognition_warnings: tuple[str, ...]

    @property
    def feature_count(self) -> int:
        return len(self.features)

    def by_type(self, feature_type: FeatureType) -> list[RecognizedFeature]:
        return [rf for rf in self.features if rf.feature.feature_type == feature_type]


class FeatureRecognitionEngine:
    """Rule-based recognition engine.

    Applies rules in priority order; each recognized feature consumes its
    source requirements so they are not double-counted.
    """

    def recognize(
        self, req_set: DrawingRequirementSet, part_id: str = "UNKNOWN"
    ) -> FeatureRecognitionResult:
        features: list[RecognizedFeature] = []
        consumed_req_ids: set[str] = set()
        warnings: list[str] = []

        # R-FR-001: Thread requirements → THREAD features
        for thread in req_set.threads:
            if thread.req_id in consumed_req_ids:
                continue
            dims: dict[str, Quantity] = {}
            if thread.nominal_diameter_mm is not None:
                dims["nominal_diameter"] = Quantity(
                    thread.nominal_diameter_mm, Unit.MM
                )
            if thread.pitch_mm is not None:
                dims["pitch"] = Quantity(thread.pitch_mm, Unit.MM)
            feat = Feature(
                feature_id=f"{req_set.source_id}-T-{thread.req_id}",
                part_id=part_id,
                feature_type=FeatureType.THREAD,
                dimensions=dims,
                provenance=_PROVENANCE,
            )
            features.append(RecognizedFeature(
                feature=feat,
                source_req_ids=(thread.req_id,),
                recognition_rule="R-FR-001",
            ))
            consumed_req_ids.add(thread.req_id)

        # R-FR-002: Diameter dimension with optional depth → HOLE
        diameter_dims = [
            d for d in req_set.dimensional
            if "diameter" in d.dimension_type.lower()
            and d.req_id not in consumed_req_ids
        ]
        for dim in diameter_dims:
            # Look for a depth pairing
            depth_dim = self._find_depth(req_set.dimensional, consumed_req_ids)
            depth_qty: Quantity | None = None
            depth_req_id: str | None = None
            if depth_dim is not None:
                depth_qty = Quantity(depth_dim.nominal_value, Unit.MM)
                depth_req_id = depth_dim.req_id

            dims = {"diameter": Quantity(dim.nominal_value, Unit.MM)}
            if depth_qty is not None:
                dims["depth"] = depth_qty

            feat = Feature(
                feature_id=f"{req_set.source_id}-H-{dim.req_id}",
                part_id=part_id,
                feature_type=FeatureType.HOLE,
                dimensions=dims,
                provenance=_PROVENANCE,
            )
            src = (dim.req_id,) + ((depth_req_id,) if depth_req_id else ())
            features.append(RecognizedFeature(
                feature=feat,
                source_req_ids=src,
                recognition_rule="R-FR-002",
            ))
            consumed_req_ids.add(dim.req_id)
            if depth_req_id:
                consumed_req_ids.add(depth_req_id)

        # R-FR-003/004: Slot / pocket from dimension notes
        remaining_dims = [
            d for d in req_set.dimensional
            if d.req_id not in consumed_req_ids
        ]
        for dim in remaining_dims:
            note_text = (dim.notes or "").lower()
            if _SLOT_RE.search(note_text) or _SLOT_RE.search(dim.dimension_type):
                dims = {"width": Quantity(dim.nominal_value, Unit.MM)}
                feat = Feature(
                    feature_id=f"{req_set.source_id}-S-{dim.req_id}",
                    part_id=part_id,
                    feature_type=FeatureType.SLOT,
                    dimensions=dims,
                    provenance=_PROVENANCE,
                )
                features.append(RecognizedFeature(
                    feature=feat,
                    source_req_ids=(dim.req_id,),
                    recognition_rule="R-FR-003",
                ))
                consumed_req_ids.add(dim.req_id)
            elif _POCKET_RE.search(note_text) or _POCKET_RE.search(dim.dimension_type):
                dims = {"width": Quantity(dim.nominal_value, Unit.MM)}
                feat = Feature(
                    feature_id=f"{req_set.source_id}-P-{dim.req_id}",
                    part_id=part_id,
                    feature_type=FeatureType.POCKET,
                    dimensions=dims,
                    provenance=_PROVENANCE,
                )
                features.append(RecognizedFeature(
                    feature=feat,
                    source_req_ids=(dim.req_id,),
                    recognition_rule="R-FR-004",
                ))
                consumed_req_ids.add(dim.req_id)
            elif _CHAMFER_RE.search(note_text) or _CHAMFER_RE.search(dim.dimension_type):
                dims = {"size": Quantity(dim.nominal_value, Unit.MM)}
                feat = Feature(
                    feature_id=f"{req_set.source_id}-CH-{dim.req_id}",
                    part_id=part_id,
                    feature_type=FeatureType.CHAMFER,
                    dimensions=dims,
                    provenance=_PROVENANCE,
                )
                features.append(RecognizedFeature(
                    feature=feat,
                    source_req_ids=(dim.req_id,),
                    recognition_rule="R-FR-007",
                ))
                consumed_req_ids.add(dim.req_id)
            elif _FILLET_RE.search(note_text) or "radius" in dim.dimension_type.lower():
                dims = {"radius": Quantity(dim.nominal_value, Unit.MM)}
                feat = Feature(
                    feature_id=f"{req_set.source_id}-F-{dim.req_id}",
                    part_id=part_id,
                    feature_type=FeatureType.FILLET,
                    dimensions=dims,
                    provenance=_PROVENANCE,
                )
                features.append(RecognizedFeature(
                    feature=feat,
                    source_req_ids=(dim.req_id,),
                    recognition_rule="R-FR-008",
                ))
                consumed_req_ids.add(dim.req_id)
            elif _GROOVE_RE.search(note_text) or _GROOVE_RE.search(dim.dimension_type):
                dims = {"width": Quantity(dim.nominal_value, Unit.MM)}
                feat = Feature(
                    feature_id=f"{req_set.source_id}-G-{dim.req_id}",
                    part_id=part_id,
                    feature_type=FeatureType.GROOVE,
                    dimensions=dims,
                    provenance=_PROVENANCE,
                )
                features.append(RecognizedFeature(
                    feature=feat,
                    source_req_ids=(dim.req_id,),
                    recognition_rule="R-FR-009",
                ))
                consumed_req_ids.add(dim.req_id)

        # R-FR-005: Cylindrical GD&T → CYLINDRICAL_SURFACE
        for geom in req_set.geometric:
            if geom.req_id in consumed_req_ids:
                continue
            if geom.fcf.characteristic in GDT_CYLINDRICAL_CONTEXT:
                dims = {
                    "gdt_tolerance": Quantity(
                        geom.fcf.tolerance_value, Unit.MM
                    )
                }
                feat = Feature(
                    feature_id=f"{req_set.source_id}-CYL-{geom.req_id}",
                    part_id=part_id,
                    feature_type=FeatureType.CYLINDRICAL_SURFACE,
                    dimensions=dims,
                    provenance=_PROVENANCE,
                )
                features.append(RecognizedFeature(
                    feature=feat,
                    source_req_ids=(geom.req_id,),
                    recognition_rule="R-FR-005",
                ))
                consumed_req_ids.add(geom.req_id)

        # R-FR-006: Flatness / parallelism GD&T → PLANAR_FACE
        flat_chars = {
            GdtCharacteristic.FLATNESS,
            GdtCharacteristic.PARALLELISM,
            GdtCharacteristic.PERPENDICULARITY,
            GdtCharacteristic.PROFILE_OF_A_SURFACE,
        }
        for geom in req_set.geometric:
            if geom.req_id in consumed_req_ids:
                continue
            if geom.fcf.characteristic in flat_chars:
                dims = {
                    "gdt_tolerance": Quantity(geom.fcf.tolerance_value, Unit.MM)
                }
                feat = Feature(
                    feature_id=f"{req_set.source_id}-PL-{geom.req_id}",
                    part_id=part_id,
                    feature_type=FeatureType.PLANAR_FACE,
                    dimensions=dims,
                    provenance=_PROVENANCE,
                )
                features.append(RecognizedFeature(
                    feature=feat,
                    source_req_ids=(geom.req_id,),
                    recognition_rule="R-FR-006",
                ))
                consumed_req_ids.add(geom.req_id)

        # R-FR-010: Remaining diameter dimensions (non-hole, e.g. OD turning)
        still_remaining = [
            d for d in req_set.dimensional
            if d.req_id not in consumed_req_ids
            and ("diameter" in d.dimension_type.lower()
                 or _BORE_RE.search(d.dimension_type))
        ]
        for dim in still_remaining:
            dims = {"diameter": Quantity(dim.nominal_value, Unit.MM)}
            feat = Feature(
                feature_id=f"{req_set.source_id}-CYL2-{dim.req_id}",
                part_id=part_id,
                feature_type=FeatureType.CYLINDRICAL_SURFACE,
                dimensions=dims,
                provenance=_PROVENANCE,
            )
            features.append(RecognizedFeature(
                feature=feat,
                source_req_ids=(dim.req_id,),
                recognition_rule="R-FR-010",
            ))
            consumed_req_ids.add(dim.req_id)

        # Collect unrecognized
        all_req_ids: set[str] = set()
        for d in req_set.dimensional:
            all_req_ids.add(d.req_id)
        for g in req_set.geometric:
            all_req_ids.add(g.req_id)
        for s in req_set.surface_finish:
            all_req_ids.add(s.req_id)
        for t in req_set.threads:
            all_req_ids.add(t.req_id)

        unrecognized = tuple(sorted(all_req_ids - consumed_req_ids))

        return FeatureRecognitionResult(
            source_id=req_set.source_id,
            features=tuple(features),
            unrecognized_req_ids=unrecognized,
            recognition_warnings=tuple(warnings),
        )

    def _find_depth(
        self,
        dimensions: tuple[DimensionalRequirement, ...],
        consumed: set[str],
    ) -> DimensionalRequirement | None:
        for d in dimensions:
            if d.req_id in consumed:
                continue
            if "depth" in d.dimension_type.lower() or "length" in d.dimension_type.lower():
                return d
        return None


def recognize_features(
    req_set: DrawingRequirementSet, part_id: str = "UNKNOWN"
) -> FeatureRecognitionResult:
    """Convenience function: recognise features from a DrawingRequirementSet."""
    return FeatureRecognitionEngine().recognize(req_set, part_id=part_id)
