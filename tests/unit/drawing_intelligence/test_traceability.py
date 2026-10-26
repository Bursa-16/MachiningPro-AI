"""Tests for drawing_intelligence.traceability (EPIC_04 Phase 2)."""

import pytest

from backend.drawing_intelligence.traceability import (
    TraceabilityChain,
    TraceabilityEntry,
    TraceabilityLedger,
)


class TestTraceabilityLedger:
    def _make_ledger(self):
        return TraceabilityLedger(
            source_id="dwg-001",
            drawing_number="DWG-100",
            revision="A",
        )

    def test_empty_ledger(self):
        ledger = self._make_ledger()
        chain = ledger.build()
        assert len(chain.entries) == 0

    def test_record_and_build(self):
        ledger = self._make_ledger()
        ledger.record(
            req_id="D-0001",
            feature_id="feat-001",
            step_id="S-0001",
            recognition_rule="R-FR-002",
            operation="DRILLING",
        )
        chain = ledger.build()
        assert len(chain.entries) == 1
        e = chain.entries[0]
        assert e.req_id == "D-0001"
        assert e.feature_id == "feat-001"
        assert e.step_id == "S-0001"

    def test_multiple_entries(self):
        ledger = self._make_ledger()
        for i in range(5):
            ledger.record(
                req_id=f"D-{i:04d}",
                feature_id=f"feat-{i}",
                step_id=f"S-{i:04d}",
                recognition_rule="R-FR-002",
                operation="DRILLING",
            )
        chain = ledger.build()
        assert len(chain.entries) == 5


class TestTraceabilityChain:
    def _make_chain(self):
        entries = (
            TraceabilityEntry(
                req_id="D-0001",
                feature_id="feat-A",
                step_id="S-0001",
                recognition_rule="R-FR-002",
                operation="DRILLING",
            ),
            TraceabilityEntry(
                req_id="D-0001",
                feature_id="feat-A",
                step_id="S-0002",
                recognition_rule="R-FR-002",
                operation="REAMING",
            ),
            TraceabilityEntry(
                req_id="G-0001",
                feature_id="feat-B",
                step_id="S-0003",
                recognition_rule="R-FR-006",
                operation="MILLING",
            ),
        )
        return TraceabilityChain(
            source_id="dwg-001",
            drawing_number="DWG-001",
            revision="A",
            entries=entries,
        )

    def test_by_req(self):
        chain = self._make_chain()
        entries = chain.by_req("D-0001")
        assert len(entries) == 2

    def test_by_feature(self):
        chain = self._make_chain()
        entries = chain.by_feature("feat-A")
        assert len(entries) == 2

    def test_by_step(self):
        chain = self._make_chain()
        entries = chain.by_step("S-0003")
        assert len(entries) == 1
        assert entries[0].operation == "MILLING"

    def test_by_req_missing_returns_empty(self):
        chain = self._make_chain()
        assert chain.by_req("X-9999") == []

    def test_entries_immutable(self):
        chain = self._make_chain()
        # TraceabilityChain is frozen; entries is a tuple
        assert isinstance(chain.entries, tuple)
