"""Stage 4A: AdapterRegistry tests.

Verifies deterministic registration, exact-ID lookup, collection queries,
capability filtering, and fail-closed behaviours.  All adapters are stubs.
"""

from __future__ import annotations

import pytest

from backend.interoperability.adapter import FormatAdapter
from backend.interoperability.enums import (
    AdapterCapability,
    AdapterLicense,
    CapabilityLevel,
    FidelityReportCompleteness,
    NormalizationStatus,
)
from backend.interoperability.models import (
    AdapterMetadata,
    CanonicalDocument,
    ConversionFidelityReport,
)
from backend.interoperability.registry import AdapterRegistry, AdapterRegistryError

# ---------------------------------------------------------------------------
# Stub adapters
# ---------------------------------------------------------------------------

def _make_adapter(
    adapter_id: str,
    format_ids: tuple[str, ...],
    capabilities: tuple[AdapterCapability, ...] = (
        AdapterCapability.RECOGNIZE, AdapterCapability.PARSE,
    ),
    max_level: CapabilityLevel = CapabilityLevel.LEVEL_1_PARSED,
    license_: AdapterLicense = AdapterLicense.INTERNAL_PARSER,
) -> FormatAdapter:
    class _A(FormatAdapter):
        def metadata(self) -> AdapterMetadata:
            return AdapterMetadata(
                adapter_id=adapter_id,
                adapter_name=f"Adapter {adapter_id}",
                adapter_version="1.0.0",
                format_ids=format_ids,
                capabilities=capabilities,
                max_capability_level=max_level,
                adapter_license=license_,
            )
        def can_handle(self, source, format_descriptor=None): return True  # type: ignore[override]
        def ingest(self, source, format_descriptor):  # type: ignore[override]
            return CanonicalDocument(
                document_id="DOC-X", canonical_kind="X",
                source=source, format_descriptor=format_descriptor,
                adapter_id=adapter_id, adapter_version="1.0.0",
                capability_level=max_level,
                normalization_status=NormalizationStatus.SUCCESS,
                fidelity_report=ConversionFidelityReport(
                    report_id="RPT-X", source_format_id=format_ids[0],
                    adapter_id=adapter_id, adapter_version="1.0.0",
                    completeness=FidelityReportCompleteness.COMPLETE,
                    normalization_status=NormalizationStatus.SUCCESS,
                ),
            )
    return _A()


# ---------------------------------------------------------------------------
# A. Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_and_retrieve(self) -> None:
        registry = AdapterRegistry()
        adapter = _make_adapter("A1", ("FMT-A",))
        registry.register(adapter)
        assert registry.get("A1") is adapter

    def test_duplicate_id_rejected(self) -> None:
        registry = AdapterRegistry()
        registry.register(_make_adapter("A1", ("FMT-A",)))
        with pytest.raises(AdapterRegistryError, match="A1"):
            registry.register(_make_adapter("A1", ("FMT-B",)))

    def test_non_adapter_rejected(self) -> None:
        registry = AdapterRegistry()
        with pytest.raises(TypeError):
            registry.register("not-an-adapter")  # type: ignore[arg-type]

    def test_empty_registry_length(self) -> None:
        assert len(AdapterRegistry()) == 0

    def test_length_increments(self) -> None:
        registry = AdapterRegistry()
        registry.register(_make_adapter("A1", ("FMT-A",)))
        registry.register(_make_adapter("A2", ("FMT-B",)))
        assert len(registry) == 2

    def test_contains_after_register(self) -> None:
        registry = AdapterRegistry()
        registry.register(_make_adapter("A1", ("FMT-A",)))
        assert "A1" in registry
        assert "MISSING" not in registry

    def test_has(self) -> None:
        registry = AdapterRegistry()
        registry.register(_make_adapter("A1", ("FMT-A",)))
        assert registry.has("A1") is True
        assert registry.has("NOPE") is False


# ---------------------------------------------------------------------------
# B. Exact-ID lookup
# ---------------------------------------------------------------------------

class TestExactLookup:
    def test_get_existing(self) -> None:
        registry = AdapterRegistry()
        a = _make_adapter("A1", ("FMT-A",))
        registry.register(a)
        assert registry.get("A1") is a

    def test_get_missing_raises(self) -> None:
        registry = AdapterRegistry()
        with pytest.raises(AdapterRegistryError, match="GHOST"):
            registry.get("GHOST")


# ---------------------------------------------------------------------------
# C. Collection queries — deterministic ordering
# ---------------------------------------------------------------------------

class TestCollectionQueries:
    def test_all_sorted_by_adapter_id(self) -> None:
        registry = AdapterRegistry()
        registry.register(_make_adapter("Z-ADAPTER", ("FMT-Z",)))
        registry.register(_make_adapter("A-ADAPTER", ("FMT-A",)))
        all_adapters = registry.all()
        assert [a.metadata().adapter_id for a in all_adapters] == [
            "A-ADAPTER", "Z-ADAPTER"
        ]

    def test_deterministic_repeated_query(self) -> None:
        registry = AdapterRegistry()
        registry.register(_make_adapter("C-ADAPTER", ("FMT-C",)))
        registry.register(_make_adapter("A-ADAPTER", ("FMT-A",)))
        r1 = registry.all()
        r2 = registry.all()
        assert [a.metadata().adapter_id for a in r1] == [
            a.metadata().adapter_id for a in r2
        ]

    def test_find_by_format_match(self) -> None:
        registry = AdapterRegistry()
        a = _make_adapter("A1", ("STEP-AP242",))
        b = _make_adapter("B1", ("FANUC-NC",))
        registry.register(a)
        registry.register(b)
        results = registry.find_by_format("STEP-AP242")
        assert len(results) == 1
        assert results[0].metadata().adapter_id == "A1"

    def test_find_by_format_no_match_empty(self) -> None:
        registry = AdapterRegistry()
        registry.register(_make_adapter("A1", ("FMT-A",)))
        assert registry.find_by_format("NONEXISTENT") == ()

    def test_find_by_format_multiple_adapters_for_same_format(self) -> None:
        """Two adapters for the same format — both returned; no automatic pick."""
        registry = AdapterRegistry()
        a = _make_adapter("OPEN-STEP", ("STEP-AP242",))
        b = _make_adapter("COMMERCIAL-STEP", ("STEP-AP242",),
                          license_=AdapterLicense.COMMERCIAL_SDK)
        registry.register(a)
        registry.register(b)
        results = registry.find_by_format("STEP-AP242")
        assert len(results) == 2
        ids = {r.metadata().adapter_id for r in results}
        assert "OPEN-STEP" in ids
        assert "COMMERCIAL-STEP" in ids
        # Sorted by adapter_id
        assert results[0].metadata().adapter_id < results[1].metadata().adapter_id

    def test_find_by_capability(self) -> None:
        registry = AdapterRegistry()
        a = _make_adapter("A1", ("FMT-A",),
                          capabilities=(AdapterCapability.RECOGNIZE, AdapterCapability.PARSE))
        b = _make_adapter("B1", ("FMT-B",),
                          capabilities=(AdapterCapability.RECOGNIZE, AdapterCapability.EXPORT))
        registry.register(a)
        registry.register(b)
        exporters = registry.find_by_capability(AdapterCapability.EXPORT)
        assert len(exporters) == 1
        assert exporters[0].metadata().adapter_id == "B1"

    def test_find_by_capability_none_match(self) -> None:
        registry = AdapterRegistry()
        registry.register(_make_adapter("A1", ("FMT-A",)))
        assert registry.find_by_capability(AdapterCapability.CONVERT) == ()

    def test_metadata_for_all_sorted(self) -> None:
        registry = AdapterRegistry()
        registry.register(_make_adapter("Z1", ("FMT-Z",)))
        registry.register(_make_adapter("A1", ("FMT-A",)))
        metas = registry.metadata_for_all()
        assert metas[0].adapter_id == "A1"
        assert metas[1].adapter_id == "Z1"

    def test_ids_registration_order(self) -> None:
        registry = AdapterRegistry()
        registry.register(_make_adapter("FIRST", ("FMT-A",)))
        registry.register(_make_adapter("SECOND", ("FMT-B",)))
        ids = registry.ids()
        assert ids == ("FIRST", "SECOND")

    def test_empty_registry_all(self) -> None:
        assert AdapterRegistry().all() == ()


# ---------------------------------------------------------------------------
# D. No automatic adapter selection — registry is a data store only
# ---------------------------------------------------------------------------

class TestNoAutomaticSelection:
    def test_registry_never_selects_best_adapter(self) -> None:
        """find_by_format returns all; caller must choose."""
        registry = AdapterRegistry()
        registry.register(_make_adapter("OPEN", ("STEP-AP242",),
                                        max_level=CapabilityLevel.LEVEL_2_NORMALIZED))
        registry.register(_make_adapter("COMMERCIAL", ("STEP-AP242",),
                                        max_level=CapabilityLevel.LEVEL_4_MANUFACTURING_FEATURES,
                                        license_=AdapterLicense.COMMERCIAL_SDK))
        results = registry.find_by_format("STEP-AP242")
        # Both returned — registry does not pick the "better" one
        assert len(results) == 2

    def test_registry_is_not_a_singleton(self) -> None:
        r1 = AdapterRegistry()
        r2 = AdapterRegistry()
        r1.register(_make_adapter("A1", ("FMT",)))
        # r2 is independent
        assert len(r2) == 0

    def test_adapter_registered_in_r1_not_in_r2(self) -> None:
        r1 = AdapterRegistry()
        r2 = AdapterRegistry()
        r1.register(_make_adapter("A1", ("FMT",)))
        assert not r2.has("A1")


# ---------------------------------------------------------------------------
# E. AdapterRegistryError is a DomainError
# ---------------------------------------------------------------------------

class TestAdapterRegistryError:
    def test_is_domain_error(self) -> None:
        from backend.domain.exceptions import DomainError
        err = AdapterRegistryError("test")
        assert isinstance(err, DomainError)

    def test_carries_message(self) -> None:
        err = AdapterRegistryError("duplicate adapter id 'X'")
        assert "X" in str(err)
