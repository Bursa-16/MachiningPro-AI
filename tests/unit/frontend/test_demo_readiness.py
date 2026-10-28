"""Test demo readiness: demoSpool, i18n, version strings."""
import json
from pathlib import Path

DEMO_SPOOL = Path("frontend/app/src/data/demoSpool.ts")
EN_FILE = Path("frontend/app/src/i18n/en.ts")
TR_FILE = Path("frontend/app/src/i18n/tr.ts")
PKG_FILE = Path("frontend/app/package.json")
BACKEND_APP = Path("backend/api/app.py")
DEMO_GUIDE = Path("docs/DEMO_GUIDE.md")
CAPABILITY_MATRIX = Path("docs/CAPABILITY_MATRIX.md")


class TestDemoSpoolSymbols:
    def test_no_wrong_diameter_symbol(self):
        content = DEMO_SPOOL.read_text(encoding="utf-8")
        # U+2357 ⍀ is wrong; U+2300 ⌀ is correct diameter symbol
        assert "\u2357" not in content, "Wrong diameter symbol ⍀ (U+2357) found in demoSpool.ts"

    def test_customer_data_not_used(self):
        content = DEMO_SPOOL.read_text(encoding="utf-8")
        assert "CUSTOMER_DATA_USED=NO" in content

    def test_demo_spool_has_mp_demo_001(self):
        content = DEMO_SPOOL.read_text(encoding="utf-8")
        assert "MP-DEMO-001" in content


class TestI18nDemoKeys:
    def _read(self, path):
        return path.read_text(encoding="utf-8")

    def test_en_has_demo_keys(self):
        content = self._read(EN_FILE)
        for key in ["startDemo", "credentialsBtn", "engineeringDisclaimer", "pipelineStep"]:
            assert key in content, f"Missing demo i18n key containing '{key}' in en.ts"

    def test_tr_has_demo_keys(self):
        content = self._read(TR_FILE)
        for key in ["startDemo", "credentialsBtn", "engineeringDisclaimer", "pipelineStep"]:
            assert key in content, f"Missing demo i18n key containing '{key}' in tr.ts"

    def test_i18n_parity(self):
        en = self._read(EN_FILE)
        tr = self._read(TR_FILE)
        en_lines = [ln for ln in en.split("\n") if ":" in ln and not ln.strip().startswith("//")]
        tr_lines = [ln for ln in tr.split("\n") if ":" in ln and not ln.strip().startswith("//")]
        diff = abs(len(en_lines) - len(tr_lines))
        assert diff < max(10, len(en_lines) * 0.2)


class TestVersionStrings:
    def test_package_json_version(self):
        pkg = json.loads(PKG_FILE.read_text(encoding="utf-8"))
        assert pkg["version"] != "0.0.0", "package.json version is still 0.0.0"

    def test_package_json_name(self):
        pkg = json.loads(PKG_FILE.read_text(encoding="utf-8"))
        assert pkg["name"] != "app", "package.json name is still 'app'"

    def test_backend_has_demo_version(self):
        content = BACKEND_APP.read_text(encoding="utf-8")
        assert "0.5.0" in content or "0.5" in content, "Backend app.py version not updated"


class TestDocumentation:
    def test_demo_guide_updated(self):
        content = DEMO_GUIDE.read_text(encoding="utf-8")
        assert "0.5" in content, "DEMO_GUIDE.md not updated to v0.5"
        assert "MP-DEMO-001" in content, "DEMO_GUIDE.md missing demo part reference"
        assert "Drawing Parser" in content, "DEMO_GUIDE.md missing Drawing Parser reference"
        assert "Manufacturing Plan" in content, "DEMO_GUIDE.md missing Manufacturing Plan reference"

    def test_capability_matrix_exists(self):
        assert CAPABILITY_MATRIX.exists(), "CAPABILITY_MATRIX.md not created"

    def test_capability_matrix_covers_core(self):
        content = CAPABILITY_MATRIX.read_text(encoding="utf-8")
        for cap in ["Manufacturing Plan", "Inspection Plan", "Control Plan", "Process Route"]:
            assert cap in content, f"CAPABILITY_MATRIX.md missing: {cap}"


class TestSecurityBoundaries:
    def test_no_hardcoded_password_in_frontend(self):
        """Check login-related files do not contain literal password strings."""
        import re
        # Pattern: password assignment with a quoted value that looks like a real password
        password_pattern = re.compile(
            r'(password|passwd|pwd)\s*[:=]\s*["\'][^"\']{4,}["\']',
            re.IGNORECASE
        )
        login_file = Path("frontend/app/src/pages/LoginPage.tsx")
        if login_file.exists():
            content = login_file.read_text(encoding="utf-8", errors="ignore")
            # Should not have hardcoded password values (env var references are fine)
            # Filter out lines that are clearly state variable declarations (setPassword(''))
            for line in content.split("\n"):
                if password_pattern.search(line) and "VITE_" not in line and "setPassword" not in line:
                    raise AssertionError(f"Possible hardcoded password in LoginPage.tsx: {line.strip()}")

    def test_login_page_has_credentials_btn_or_env_reference(self):
        login = Path("frontend/app/src/pages/LoginPage.tsx").read_text(encoding="utf-8")
        has_env_ref = "VITE_DEMO_USERNAME" in login or "demo_credentialsBtn" in login or "credentialsBtn" in login
        assert has_env_ref, "LoginPage should reference demo credentials via env var"

    def test_demo_spool_no_private_paths(self):
        content = DEMO_SPOOL.read_text(encoding="utf-8")
        assert "C:\\Users" not in content
        assert "/home/" not in content


class TestPipelineBreadcrumb:
    def test_breadcrumb_component_exists(self):
        breadcrumb = Path("frontend/app/src/components/PipelineBreadcrumb.tsx")
        assert breadcrumb.exists(), "PipelineBreadcrumb.tsx not created"

    def test_breadcrumb_has_pipeline_steps(self):
        content = Path("frontend/app/src/components/PipelineBreadcrumb.tsx").read_text(encoding="utf-8")
        for step in ["drawing-parser", "cad-features", "process-routes", "manufacturing-plan"]:
            assert step in content, f"PipelineBreadcrumb missing step: {step}"
