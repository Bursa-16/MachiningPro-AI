"""Stage 4A: Enum tests for the interoperability layer."""

from __future__ import annotations

from backend.interoperability.enums import (
    AdapterCapability,
    AdapterLicense,
    CapabilityLevel,
    FidelityClass,
    FidelityReportCompleteness,
    FormatFamily,
    NormalizationStatus,
)


class TestFormatFamily:
    def test_all_values_are_strings(self) -> None:
        for f in FormatFamily:
            assert isinstance(f.value, str)

    def test_cad_exists(self) -> None:
        assert FormatFamily.CAD == "CAD"

    def test_nc_exists(self) -> None:
        assert FormatFamily.NC == "NC"

    def test_unknown_exists(self) -> None:
        assert FormatFamily.UNKNOWN == "UNKNOWN"

    def test_native_cad_distinct_from_cad(self) -> None:
        assert FormatFamily.NATIVE_CAD != FormatFamily.CAD

    def test_native_cam_distinct_from_cam(self) -> None:
        assert FormatFamily.NATIVE_CAM != FormatFamily.CAM


class TestAdapterCapability:
    def test_all_values_are_strings(self) -> None:
        for c in AdapterCapability:
            assert isinstance(c.value, str)

    def test_recognize_exists(self) -> None:
        assert AdapterCapability.RECOGNIZE == "RECOGNIZE"

    def test_export_and_convert_distinct(self) -> None:
        assert AdapterCapability.EXPORT != AdapterCapability.CONVERT


class TestCapabilityLevel:
    def test_all_levels_present(self) -> None:
        levels = {cl.value for cl in CapabilityLevel}
        assert "LEVEL_0_RECOGNIZED" in levels
        assert "LEVEL_7_CONVERTED_WITH_FIDELITY_REPORT" in levels
        assert len(levels) == 8

    def test_all_values_are_strings(self) -> None:
        for cl in CapabilityLevel:
            assert isinstance(cl.value, str)


class TestAdapterLicense:
    def test_open_source_exists(self) -> None:
        assert AdapterLicense.OPEN_SOURCE == "OPEN_SOURCE"

    def test_vendor_api_distinct_from_commercial_sdk(self) -> None:
        assert AdapterLicense.VENDOR_API != AdapterLicense.COMMERCIAL_SDK


class TestFidelityClass:
    def test_all_classes_present(self) -> None:
        classes = {fc.value for fc in FidelityClass}
        assert "PRESERVED" in classes
        assert "LOST" in classes
        assert "INFERRED" in classes
        assert "DOWNGRADED" in classes

    def test_all_values_are_strings(self) -> None:
        for fc in FidelityClass:
            assert isinstance(fc.value, str)


class TestFidelityReportCompleteness:
    def test_three_states(self) -> None:
        values = {c.value for c in FidelityReportCompleteness}
        assert values == {"COMPLETE", "PARTIAL", "UNKNOWN"}


class TestNormalizationStatus:
    def test_five_states_present(self) -> None:
        values = {s.value for s in NormalizationStatus}
        assert "SUCCESS" in values
        assert "FAILED" in values
        assert "INSUFFICIENT_DATA" in values
