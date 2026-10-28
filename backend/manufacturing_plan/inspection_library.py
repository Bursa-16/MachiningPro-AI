"""Inspection method library — bounded advisory methods.

FABRICATED_GAGE_CAPABILITY=NO
UNKNOWN_CAPABILITY_TREATED_AS_SUPPORTED=NO
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.manufacturing_plan.characteristic import CharacteristicType
from backend.manufacturing_plan.characteristic_links import InspectionMethodSuitability


class InspectionMethod(StrEnum):
    CALIPER = "CALIPER"
    MICROMETER = "MICROMETER"
    BORE_GAUGE = "BORE_GAUGE"
    HEIGHT_GAUGE = "HEIGHT_GAUGE"
    DIAL_INDICATOR = "DIAL_INDICATOR"
    DIAL_INDICATOR_V_BLOCK = "DIAL_INDICATOR_V_BLOCK"
    THREAD_GAUGE = "THREAD_GAUGE"
    SURFACE_ROUGHNESS_TESTER = "SURFACE_ROUGHNESS_TESTER"
    CMM = "CMM"
    CMM_CONTOUR_SCAN = "CMM_CONTOUR_SCAN"
    ROUNDNESS_TESTER = "ROUNDNESS_TESTER"
    FORM_TESTER = "FORM_TESTER"
    PROFILE_MEASUREMENT = "PROFILE_MEASUREMENT"
    FUNCTIONAL_GAUGE = "FUNCTIONAL_GAUGE"
    HARDNESS_TESTER = "HARDNESS_TESTER"
    GO_NO_GO_GAUGE = "GO_NO_GO_GAUGE"
    SIZE_MEASUREMENT = "SIZE_MEASUREMENT"
    OPTICAL_COMPARATOR = "OPTICAL_COMPARATOR"
    VISUAL = "VISUAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class InspectionMethodRecord:
    method: InspectionMethod
    measurable_types: tuple[str, ...]
    resolution_um: float | None
    typical_range_mm: tuple[float, float] | None
    gdt_characteristics: tuple[str, ...]
    confidence: str = "LITERATURE_REFERENCE"
    notes: str = ""


INSPECTION_METHOD_LIBRARY: dict[str, InspectionMethodRecord] = {
    InspectionMethod.CALIPER: InspectionMethodRecord(
        method=InspectionMethod.CALIPER,
        measurable_types=(CharacteristicType.DIMENSION,),
        resolution_um=20.0,
        typical_range_mm=(0.0, 300.0),
        gdt_characteristics=(),
        notes="General dimensional. Not suitable below ~20µm tolerance.",
    ),
    InspectionMethod.MICROMETER: InspectionMethodRecord(
        method=InspectionMethod.MICROMETER,
        measurable_types=(CharacteristicType.DIMENSION, CharacteristicType.FIT),
        resolution_um=1.0,
        typical_range_mm=(0.0, 300.0),
        gdt_characteristics=(),
        notes="Precision external diameter/length. 1µm resolution.",
    ),
    InspectionMethod.BORE_GAUGE: InspectionMethodRecord(
        method=InspectionMethod.BORE_GAUGE,
        measurable_types=(CharacteristicType.DIMENSION, CharacteristicType.FIT),
        resolution_um=1.0,
        typical_range_mm=(3.0, 500.0),
        gdt_characteristics=(),
        notes="Internal diameter. Suitable for tight-tolerance bores.",
    ),
    InspectionMethod.HEIGHT_GAUGE: InspectionMethodRecord(
        method=InspectionMethod.HEIGHT_GAUGE,
        measurable_types=(CharacteristicType.DIMENSION,),
        resolution_um=10.0,
        typical_range_mm=(0.0, 1000.0),
        gdt_characteristics=("FLATNESS",),
        notes="Step heights, flatness on surface plate.",
    ),
    InspectionMethod.DIAL_INDICATOR: InspectionMethodRecord(
        method=InspectionMethod.DIAL_INDICATOR,
        measurable_types=(CharacteristicType.GDT, CharacteristicType.DIMENSION),
        resolution_um=1.0,
        typical_range_mm=(0.0, 50.0),
        gdt_characteristics=("FLATNESS", "PARALLELISM", "CIRCULAR_RUNOUT", "TOTAL_RUNOUT"),
        notes="Comparative measurement; needs reference datum.",
    ),
    InspectionMethod.DIAL_INDICATOR_V_BLOCK: InspectionMethodRecord(
        method=InspectionMethod.DIAL_INDICATOR_V_BLOCK,
        measurable_types=(CharacteristicType.GDT,),
        resolution_um=1.0,
        typical_range_mm=(3.0, 200.0),
        gdt_characteristics=("CIRCULAR_RUNOUT", "TOTAL_RUNOUT", "CYLINDRICITY"),
        notes="Runout check on V-block. Requires cylindrical datum.",
    ),
    InspectionMethod.THREAD_GAUGE: InspectionMethodRecord(
        method=InspectionMethod.THREAD_GAUGE,
        measurable_types=(CharacteristicType.THREAD,),
        resolution_um=None,
        typical_range_mm=None,
        gdt_characteristics=(),
        notes="Go/no-go thread gauge for metric/unified/pipe.",
    ),
    InspectionMethod.SURFACE_ROUGHNESS_TESTER: InspectionMethodRecord(
        method=InspectionMethod.SURFACE_ROUGHNESS_TESTER,
        measurable_types=(CharacteristicType.SURFACE_FINISH,),
        resolution_um=0.01,
        typical_range_mm=None,
        gdt_characteristics=(),
        notes="Contact profilometer. Ra/Rz measurement.",
    ),
    InspectionMethod.CMM: InspectionMethodRecord(
        method=InspectionMethod.CMM,
        measurable_types=(
            CharacteristicType.DIMENSION, CharacteristicType.GDT, CharacteristicType.FIT,
        ),
        resolution_um=0.1,
        typical_range_mm=(0.1, 5000.0),
        gdt_characteristics=(
            "STRAIGHTNESS", "FLATNESS", "CIRCULARITY", "CYLINDRICITY",
            "PERPENDICULARITY", "ANGULARITY", "PARALLELISM",
            "POSITION", "CONCENTRICITY", "SYMMETRY",
            "CIRCULAR_RUNOUT", "TOTAL_RUNOUT",
        ),
        notes="CMM — comprehensive GD&T and dimensional capability.",
    ),
    InspectionMethod.CMM_CONTOUR_SCAN: InspectionMethodRecord(
        method=InspectionMethod.CMM_CONTOUR_SCAN,
        measurable_types=(CharacteristicType.GDT,),
        resolution_um=0.1,
        typical_range_mm=None,
        gdt_characteristics=("PROFILE_OF_A_LINE", "PROFILE_OF_A_SURFACE"),
        notes="CMM contour scanning for profile tolerances.",
    ),
    InspectionMethod.ROUNDNESS_TESTER: InspectionMethodRecord(
        method=InspectionMethod.ROUNDNESS_TESTER,
        measurable_types=(CharacteristicType.GDT,),
        resolution_um=0.01,
        typical_range_mm=(0.5, 500.0),
        gdt_characteristics=("CIRCULARITY", "CYLINDRICITY"),
        notes="Spindle-based roundness. Best for circularity/cylindricity.",
    ),
    InspectionMethod.FORM_TESTER: InspectionMethodRecord(
        method=InspectionMethod.FORM_TESTER,
        measurable_types=(CharacteristicType.GDT,),
        resolution_um=0.01,
        typical_range_mm=None,
        gdt_characteristics=("STRAIGHTNESS", "FLATNESS", "CYLINDRICITY"),
        notes="General form measurement.",
    ),
    InspectionMethod.FUNCTIONAL_GAUGE: InspectionMethodRecord(
        method=InspectionMethod.FUNCTIONAL_GAUGE,
        measurable_types=(CharacteristicType.GDT, CharacteristicType.FIT),
        resolution_um=None,
        typical_range_mm=None,
        gdt_characteristics=("POSITION",),
        notes="Purpose-made gauge. High quantity production. Go/no-go.",
    ),
    InspectionMethod.HARDNESS_TESTER: InspectionMethodRecord(
        method=InspectionMethod.HARDNESS_TESTER,
        measurable_types=(CharacteristicType.HARDNESS,),
        resolution_um=None,
        typical_range_mm=None,
        gdt_characteristics=(),
        notes="Rockwell/Brinell/Vickers hardness.",
    ),
    InspectionMethod.GO_NO_GO_GAUGE: InspectionMethodRecord(
        method=InspectionMethod.GO_NO_GO_GAUGE,
        measurable_types=(CharacteristicType.DIMENSION, CharacteristicType.FIT),
        resolution_um=None,
        typical_range_mm=None,
        gdt_characteristics=(),
        notes="Go/no-go limit gauge for diameter/fit.",
    ),
    InspectionMethod.SIZE_MEASUREMENT: InspectionMethodRecord(
        method=InspectionMethod.SIZE_MEASUREMENT,
        measurable_types=(CharacteristicType.DIMENSION, CharacteristicType.FIT),
        resolution_um=1.0,
        typical_range_mm=None,
        gdt_characteristics=(),
        notes="Pre-check for MMC/LMC modifier.",
    ),
    InspectionMethod.OPTICAL_COMPARATOR: InspectionMethodRecord(
        method=InspectionMethod.OPTICAL_COMPARATOR,
        measurable_types=(CharacteristicType.GDT, CharacteristicType.DIMENSION),
        resolution_um=5.0,
        typical_range_mm=None,
        gdt_characteristics=("PROFILE_OF_A_LINE",),
        notes="Optical profile projector for form and geometry verification.",
    ),
    InspectionMethod.PROFILE_MEASUREMENT: InspectionMethodRecord(
        method=InspectionMethod.PROFILE_MEASUREMENT,
        measurable_types=(CharacteristicType.GDT,),
        resolution_um=0.5,
        typical_range_mm=None,
        gdt_characteristics=("PROFILE_OF_A_LINE", "PROFILE_OF_A_SURFACE"),
        notes="Optical or tactile profile measurement for profile tolerances.",
    ),
    InspectionMethod.VISUAL: InspectionMethodRecord(
        method=InspectionMethod.VISUAL,
        measurable_types=(CharacteristicType.COATING, CharacteristicType.SPECIAL_NOTE),
        resolution_um=None,
        typical_range_mm=None,
        gdt_characteristics=(),
        notes="Visual/cosmetic inspection.",
    ),
    InspectionMethod.UNKNOWN: InspectionMethodRecord(
        method=InspectionMethod.UNKNOWN,
        measurable_types=(),
        resolution_um=None,
        typical_range_mm=None,
        gdt_characteristics=(),
        notes="Method not yet determined.",
    ),
}


def method_suitability(
    method: str,
    char_type: CharacteristicType,
    tolerance_um: float | None,
    nominal_size_mm: float | None,
) -> InspectionMethodSuitability:
    """Evaluate suitability of a method for a characteristic.

    UNKNOWN_CAPABILITY_TREATED_AS_SUPPORTED=NO
    """
    rec = INSPECTION_METHOD_LIBRARY.get(method)
    if rec is None or method == InspectionMethod.UNKNOWN:
        return InspectionMethodSuitability.INSUFFICIENT_DATA

    type_val = char_type.value if hasattr(char_type, "value") else str(char_type)
    if type_val not in rec.measurable_types and char_type not in rec.measurable_types:
        if char_type == CharacteristicType.GDT and rec.gdt_characteristics:
            return InspectionMethodSuitability.CONDITIONAL
        return InspectionMethodSuitability.NOT_SUITABLE

    if method == InspectionMethod.CALIPER and tolerance_um is not None:
        if tolerance_um < 10:
            return InspectionMethodSuitability.NOT_SUITABLE
        if tolerance_um < 20:
            return InspectionMethodSuitability.CONDITIONAL

    if method == InspectionMethod.CMM and nominal_size_mm is not None and nominal_size_mm < 3:
        return InspectionMethodSuitability.CONDITIONAL

    if method == InspectionMethod.BORE_GAUGE and nominal_size_mm is not None and nominal_size_mm < 3:
        return InspectionMethodSuitability.CONDITIONAL

    return InspectionMethodSuitability.SUITABLE


@dataclass
class GageSuggestion:
    method: InspectionMethod
    suitability: InspectionMethodSuitability
    rationale: str
    quantity_note: str | None = None
    confidence: str = "LITERATURE_REFERENCE"


def gage_suggestions(
    char_type: CharacteristicType,
    nominal_size_mm: float | None,
    tolerance_um: float | None,
    gdt_type: str | None,
    production_quantity: int | None,
) -> list[GageSuggestion]:
    """Advisory gage candidates. FABRICATED_GAGE_CAPABILITY=NO."""
    if char_type == CharacteristicType.SURFACE_FINISH:
        return [GageSuggestion(
            method=InspectionMethod.SURFACE_ROUGHNESS_TESTER,
            suitability=InspectionMethodSuitability.SUITABLE,
            rationale="Contact profilometer for Ra/Rz measurement",
        )]

    if char_type == CharacteristicType.THREAD:
        return [GageSuggestion(
            method=InspectionMethod.THREAD_GAUGE,
            suitability=InspectionMethodSuitability.SUITABLE,
            rationale="Go/no-go thread gauge",
        )]

    if char_type == CharacteristicType.HARDNESS:
        return [GageSuggestion(
            method=InspectionMethod.HARDNESS_TESTER,
            suitability=InspectionMethodSuitability.SUITABLE,
            rationale="Rockwell/Brinell/Vickers hardness tester",
        )]

    if char_type in (CharacteristicType.COATING, CharacteristicType.SPECIAL_NOTE,
                     CharacteristicType.MATERIAL):
        return [GageSuggestion(
            method=InspectionMethod.VISUAL,
            suitability=InspectionMethodSuitability.SUITABLE,
            rationale="Visual/cosmetic inspection",
        )]

    if char_type == CharacteristicType.GDT and gdt_type:
        if gdt_type == "POSITION":
            result = [GageSuggestion(
                method=InspectionMethod.CMM,
                suitability=InspectionMethodSuitability.SUITABLE,
                rationale="CMM for position tolerance",
            )]
            if production_quantity and production_quantity > 100:
                result.append(GageSuggestion(
                    method=InspectionMethod.FUNCTIONAL_GAUGE,
                    suitability=InspectionMethodSuitability.CONDITIONAL,
                    rationale="Functional gauge cost-effective at high volume",
                    quantity_note=f"Suitable for qty > 100 (current: {production_quantity})",
                ))
            return result
        if gdt_type in ("CIRCULARITY", "CYLINDRICITY"):
            return [
                GageSuggestion(method=InspectionMethod.ROUNDNESS_TESTER,
                               suitability=InspectionMethodSuitability.SUITABLE,
                               rationale="Roundness tester for circularity/cylindricity"),
                GageSuggestion(method=InspectionMethod.CMM,
                               suitability=InspectionMethodSuitability.SUITABLE,
                               rationale="CMM alternative"),
            ]
        if gdt_type in ("CIRCULAR_RUNOUT", "TOTAL_RUNOUT"):
            return [
                GageSuggestion(method=InspectionMethod.DIAL_INDICATOR_V_BLOCK,
                               suitability=InspectionMethodSuitability.SUITABLE,
                               rationale="Dial indicator on V-block for runout"),
                GageSuggestion(method=InspectionMethod.CMM,
                               suitability=InspectionMethodSuitability.SUITABLE,
                               rationale="CMM alternative for runout"),
            ]
        if gdt_type in ("PROFILE_OF_A_LINE", "PROFILE_OF_A_SURFACE"):
            return [GageSuggestion(method=InspectionMethod.CMM_CONTOUR_SCAN,
                                   suitability=InspectionMethodSuitability.SUITABLE,
                                   rationale="CMM contour scan for profile tolerance")]
        return [GageSuggestion(method=InspectionMethod.CMM,
                               suitability=InspectionMethodSuitability.SUITABLE,
                               rationale=f"CMM for {gdt_type}")]

    # DIMENSION / FIT
    if tolerance_um is None:
        return [GageSuggestion(
            method=InspectionMethod.CMM,
            suitability=InspectionMethodSuitability.INSUFFICIENT_DATA,
            rationale="Tolerance unknown — CMM provides broadest capability",
        )]

    if tolerance_um >= 200:
        return [GageSuggestion(method=InspectionMethod.CALIPER,
                               suitability=InspectionMethodSuitability.SUITABLE,
                               rationale=f"Tolerance {tolerance_um:.0f}µm suitable for caliper")]
    if tolerance_um >= 50:
        return [GageSuggestion(method=InspectionMethod.MICROMETER,
                               suitability=InspectionMethodSuitability.SUITABLE,
                               rationale=f"Tolerance {tolerance_um:.0f}µm requires micrometer")]
    if tolerance_um >= 10:
        result = []
        if nominal_size_mm and nominal_size_mm > 3:
            result.append(GageSuggestion(method=InspectionMethod.BORE_GAUGE,
                                         suitability=InspectionMethodSuitability.SUITABLE,
                                         rationale=f"Tolerance {tolerance_um:.0f}µm — bore gauge for internal"))
        result.append(GageSuggestion(method=InspectionMethod.CMM,
                                     suitability=InspectionMethodSuitability.SUITABLE,
                                     rationale="CMM for tight tolerance"))
        return result

    return [GageSuggestion(method=InspectionMethod.CMM,
                           suitability=InspectionMethodSuitability.SUITABLE,
                           rationale=f"Tolerance {tolerance_um:.1f}µm requires CMM")]
