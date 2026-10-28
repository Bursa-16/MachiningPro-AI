"""Test that pipeline i18n keys exist in both en.ts and tr.ts."""
from pathlib import Path

EN_FILE = Path("frontend/app/src/i18n/en.ts")
TR_FILE = Path("frontend/app/src/i18n/tr.ts")

REQUIRED_SUBSTRINGS = [
    "loadDemoPart",
    "continueToFeatureRecognition",
    "continueToRouteGeneration",
    "generateManufacturingPlan",
    "demoModeBanner",
    "ncHandoffExport",
    "stepLevel2Missing",
]


class TestI18nCoverage:
    def test_en_has_pipeline_keys(self):
        content = EN_FILE.read_text(encoding="utf-8")
        for key in REQUIRED_SUBSTRINGS:
            assert key in content, f"Missing i18n key in en.ts: {key}"

    def test_tr_has_pipeline_keys(self):
        content = TR_FILE.read_text(encoding="utf-8")
        for key in REQUIRED_SUBSTRINGS:
            assert key in content, f"Missing i18n key in tr.ts: {key}"

    def test_en_and_tr_have_same_key_count(self):
        en_content = EN_FILE.read_text(encoding="utf-8")
        tr_content = TR_FILE.read_text(encoding="utf-8")
        # Rough parity check — both should have similar number of lines
        en_lines = [ln for ln in en_content.split("\n") if ":" in ln and not ln.strip().startswith("//")]
        tr_lines = [ln for ln in tr_content.split("\n") if ":" in ln and not ln.strip().startswith("//")]
        # Allow 20% divergence
        diff = abs(len(en_lines) - len(tr_lines))
        assert diff < max(10, len(en_lines) * 0.2), \
            f"EN ({len(en_lines)}) and TR ({len(tr_lines)}) key counts diverge significantly"
