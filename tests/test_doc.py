"""Documentation / packaging-doc assertions.

These tests guard against drift in:

- `README.md` headline — must NOT claim PGP/AES (US-X01).
- `CHANGELOG.md` structure — `[Unreleased]` slot ready for Phase 6,
  `[0.0.7]` Phase 1 release notes mention NDJSON.
- `dependabot.yml` — weekly cadence and sane targets (US-X02).
- Release shell scripts — present, syntactically valid, mention the
  expected port (US-PKG02, US-PKG03).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# README (US-X01)
# ---------------------------------------------------------------------------


def test_readme_no_pgp_or_aes_headline_claim() -> None:
    """The README headline may not promise encryption the code never shipped."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    # Look at the first 20 lines, where the headline lives.
    headline = "\n".join(readme.splitlines()[:20])
    assert not re.search(r"\bPGP\b", headline, re.IGNORECASE), (
        "README headline still mentions PGP — drop the claim or implement "
        "PGP end-to-end. See US-X01."
    )
    assert not re.search(r"\bAES\b", headline, re.IGNORECASE), (
        "README headline still mentions AES — drop the claim or implement "
        "AES end-to-end. See US-X01."
    )


def test_readme_acknowledges_encryption_is_planned() -> None:
    """If encryption is referenced, it must say 'planned' (or equivalent)."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8").lower()
    # Either no mention at all, or framed as a future plan.
    if "encrypt" in readme:
        assert "planned" in readme or "future" in readme, (
            "README references encryption but doesn't say it's a future "
            "release — add a 'planned for a future release' note. See US-X01."
        )


# ---------------------------------------------------------------------------
# CHANGELOG (US-X03)
# ---------------------------------------------------------------------------


def test_changelog_follows_keep_a_changelog_format() -> None:
    """Top-level file shape must match Keep a Changelog 1.1+."""
    cl = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert cl.startswith("# Changelog"), (
        "CHANGELOG.md must start with '# Changelog'."
    )
    assert "[Unreleased]" in cl, (
        "CHANGELOG.md must reserve a [Unreleased] section for Phase 6 fixes."
    )
    for header in ("### Added", "### Changed", "### Fixed", "### Removed"):
        assert header in cl, f"CHANGELOG.md must contain a `{header}` subsection."


def test_changelog_has_0_0_7_phase_1_release_section() -> None:
    cl = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(r"^##\s+\[0\.0\.7\]", cl, re.MULTILINE), (
        "CHANGELOG.md must contain a `## [0.0.7]` section for the Phase 1 "
        "release — see US-X03."
    )


def test_changelog_0_0_7_mentions_ndjson_framing() -> None:
    """The Phase 1 release notes must mention the NDJSON wire protocol."""
    cl = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8").lower()
    assert "ndjson" in cl, (
        "CHANGELOG.md Phase 1 entry must mention NDJSON framing — that's "
        "the wire-protocol breaking change users must know about. See US-X03."
    )


def test_changelog_unreleased_links_to_test_report() -> None:
    """The [Unreleased] section explains how to populate it from TEST_REPORT.md."""
    cl = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "TEST_REPORT.md" in cl, (
        "CHANGELOG.md [Unreleased] section must reference TEST_REPORT.md so "
        "Phase 6 entries stay in lockstep with SXX-FAIL markers."
    )


# ---------------------------------------------------------------------------
# dependabot (US-X02)
# ---------------------------------------------------------------------------


def test_dependabot_config_present() -> None:
    cfg = REPO_ROOT / ".github" / "dependabot.yml"
    assert cfg.is_file(), (
        ".github/dependabot.yml missing — Dependabot weekly updates disabled."
    )


def test_dependabot_targets_pip_and_github_actions() -> None:
    """Dependabot must watch both the Python ecosystem and GitHub Actions."""
    cfg = (REPO_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    assert "pip" in cfg, "dependabot.yml must include a `pip` ecosystem entry."
    assert "github-actions" in cfg or "github_actions" in cfg, (
        "dependabot.yml must include a `github-actions` ecosystem entry."
    )


# ---------------------------------------------------------------------------
# Release shell scripts (US-PKG02, US-PKG03)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "script",
    ["pypi_deploy.sh", "s2c_server.sh"],
    ids=["pypi_deploy.sh", "s2c_server.sh"],
)
def test_release_script_present(script: str) -> None:
    assert (REPO_ROOT / script).is_file(), f"{script} is missing from repo root."


@pytest.mark.parametrize(
    "script",
    ["pypi_deploy.sh", "s2c_server.sh"],
    ids=["pypi_deploy.sh", "s2c_server.sh"],
)
def test_release_script_parses(script: str) -> None:
    """`bash -n` checks syntax without executing — safe in CI."""
    result = subprocess.run(
        ["bash", "-n", str(REPO_ROOT / script)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (
        f"{script} has shell syntax errors:\n{result.stderr}"
    )


def test_pypi_deploy_sh_references_publish_tool() -> None:
    """Without twine / `python -m twine` the script can't actually publish."""
    text = (REPO_ROOT / "pypi_deploy.sh").read_text(encoding="utf-8")
    assert "twine" in text or "setup.py" in text, (
        "pypi_deploy.sh must mention `twine` (or invoke setup.py) — it's "
        "the actual shipping step. US-PKG02 regression."
    )


def test_s2c_server_sh_references_default_port() -> None:
    """The launch script must bind the canonical default (port 1122)."""
    text = (REPO_ROOT / "s2c_server.sh").read_text(encoding="utf-8")
    assert "1122" in text, (
        "s2c_server.sh must bind port 1122 (the documented default) — "
        "US-PKG02 / US-PKG03 regression."
    )


# ---------------------------------------------------------------------------
# TEST_REPORT.md landing zone is alive
# ---------------------------------------------------------------------------


def test_test_report_has_required_landing_zones() -> None:
    """TEST_REPORT.md is the Phase 5 collector — must contain Failures + Skips."""
    tr = (REPO_ROOT / "TEST_REPORT.md").read_text(encoding="utf-8")
    assert "## Failures" in tr, "TEST_REPORT.md missing the Failures section."
    assert "## Skips" in tr, "TEST_REPORT.md missing the Skips section."
    assert "SXX-FAIL" in tr, (
        "TEST_REPORT.md must document the SXX-FAIL block schema."
    )
