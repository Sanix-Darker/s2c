"""Drift guard tests — the same checks as
``scripts/changelog_drift.py``, exposed through pytest fixtures so the
guard fails locally on every test run (not just CI).

Two layers:

* ``test_repo_drift_free`` — runs the drift check against the live repo
  files. Asserts the current state has zero drift (Phase 5 left the
  ``SXX-FAIL`` set empty, but this test re-binds whenever a FAIL does
  exist so it stays in lock-step).
* Negative tests — synthesise stripped-down TEST_REPORT.md and
  CHANGELOG.md pairs under ``tmp_path`` and assert each kind of drift
  is detected (SXX-FAIL id missing from Fixed; ALREADY-FIXED-but-Fixed
  also removed; CHANGELOG without an `[Unreleased]` section;
  TEST_REPORT without any FAIL blocks).
"""

from __future__ import annotations

import textwrap

import pytest

from scripts.changelog_drift import (
    collect_fail_ids,
    collect_fixed_ids,
    collect_subsection,
    check_drift,
    main as drift_main,
)


# ---------------------------------------------------------------------------
# Negative fixture builders
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_reporter(tmp_path):
    """Write a stripped-down TEST_REPORT.md into tmp_path; return its path."""
    p = tmp_path / "TEST_REPORT.md"
    p.write_text(textwrap.dedent("""\
        # TEST_REPORT

        ### US-S05-FAIL: tcp framing crash
        - **Status**: 🔴

        ### US-S07-FAIL: missing tracing in handler
        - **Status**: 🔴
    """), encoding="utf-8")
    return p


@pytest.fixture
def minimal_changelog_unreleased_only(tmp_path):
    """CHANGELOG with `[Unreleased]` but no `Fixed` subsection."""
    p = tmp_path / "CHANGELOG.md"
    p.write_text(textwrap.dedent("""\
        # Changelog

        ## [Unreleased]

        Nothing yet.
    """), encoding="utf-8")
    return p


@pytest.fixture
def minimal_changelog_fixed_for_s05_only(tmp_path):
    """CHANGELOG with `[Unreleased] → Fixed` mentioning only US-S05."""
    p = tmp_path / "CHANGELOG.md"
    p.write_text(textwrap.dedent("""\
        # Changelog

        ## [Unreleased]

        ### Fixed

        - `Server.Framer` rewritten; partial/coalesced segments no longer
          crash `json.loads` (#US-S05).
    """), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Live-repo check (the one the CI guard cares about)
# ---------------------------------------------------------------------------


def test_repo_drift_free() -> None:
    """The shipped TEST_REPORT.md must have every SXX-FAIL mirrored."""
    missing, _fail_count = check_drift()
    assert missing == [], (
        "CHANGELOG drift detected — these SXX-FAIL story ids lack a "
        "`(#US-XX)` reference under `[Unreleased] → Fixed`: "
        f"{missing}"
    )


# ---------------------------------------------------------------------------
# Parser unit tests
# ---------------------------------------------------------------------------


def test_collect_fail_ids_returns_full_ids_in_order() -> None:
    report = textwrap.dedent("""\
        ### US-S05-FAIL: a
        stuff
        ### US-X01-FAIL: b
        stuff
    """)
    assert collect_fail_ids(report) == ["US-S05-FAIL", "US-X01-FAIL"]


def test_collect_subsection_handles_missing_top_header() -> None:
    assert collect_subsection("# nothing here", top_header="[Unreleased]",
                             subsection="Fixed") is None


def test_collect_subsection_handles_missing_subsection() -> None:
    text = "## [Unreleased]\n\nNotes only.\n"
    assert collect_subsection(
        text, top_header="[Unreleased]", subsection="Fixed",
    ) is None


def test_collect_fixed_ids_reads_only_fixed_subsection() -> None:
    cl = textwrap.dedent("""\
        ## [Unreleased]

        ### Added

        - Some new thing (#US-S09).

        ### Fixed

        - First fix (#US-S05).
        - Second fix (#US-S07).
    """)
    assert collect_fixed_ids(cl) == ["US-S05", "US-S07"]


# ---------------------------------------------------------------------------
# Negative drift detection (via tmp_path)
# ---------------------------------------------------------------------------


def test_drift_detected_when_fail_has_no_fixed_bullet(
    minimal_reporter, minimal_changelog_unreleased_only,
) -> None:
    """Both FAILs are present in TEST_REPORT, neither has a Fixed bullet."""
    missing, _fail_count = check_drift(
        minimal_reporter, minimal_changelog_unreleased_only,
    )
    assert missing == ["US-S05", "US-S07"], (
        f"Expected both fail ids to be flagged as missing; got {missing!r}"
    )


def test_drift_partial_when_only_some_fails_are_mirrored(
    minimal_reporter, minimal_changelog_fixed_for_s05_only,
) -> None:
    """US-S05 is mirrored; US-S07 still missing → drift reports US-S07 only."""
    missing, _fail_count = check_drift(
        minimal_reporter, minimal_changelog_fixed_for_s05_only,
    )
    assert missing == ["US-S07"], (
        f"Expected only US-S07 to be flagged missable; got {missing!r}"
    )


def test_drift_clean_when_every_fail_is_mirrored(
    tmp_path, minimal_reporter,
) -> None:
    cl = tmp_path / "CHANGELOG.md"
    cl.write_text(textwrap.dedent("""\
        # Changelog
        ## [Unreleased]
        ### Fixed
        - (#US-S05)
        - (#US-S07)
    """), encoding="utf-8")
    missing, _fail_count = check_drift(minimal_reporter, cl)
    assert missing == []


def test_drift_clean_when_test_report_has_no_fail_blocks(tmp_path) -> None:
    """No SXX-FAIL → no drift (Fixed bullets are not required)."""
    tr = tmp_path / "TEST_REPORT.md"
    tr.write_text("# TEST_REPORT\n\nNo fails.\n", encoding="utf-8")
    cl = tmp_path / "CHANGELOG.md"
    cl.write_text(
        "# Changelog\n## [Unreleased]\n### Fixed\n- (#US-S05)\n",
        encoding="utf-8",
    )
    missing, _fail_count = check_drift(tr, cl)
    assert missing == []


# ---------------------------------------------------------------------------
# CLI smoke — exit codes only (avoid asserting on stderr via capsys).
# ---------------------------------------------------------------------------


def test_drift_cli_exits_zero_when_repo_is_clean() -> None:
    """`python scripts/changelog_drift.py` exits 0 on the shipped docs."""
    # Drive the CLI with the default paths — no monkeypatching needed.
    rc = drift_main(["--quiet"])
    assert rc == 0, (
        f"scripts/changelog_drift.py exited {rc}"
    )


def test_drift_cli_exits_one_when_minimal_fail_is_unmirrored(
    monkeypatch: pytest.MonkeyPatch,
    minimal_reporter,
    minimal_changelog_unreleased_only,
) -> None:
    rc = drift_main([
        "--test-report", str(minimal_reporter),
        "--changelog", str(minimal_changelog_unreleased_only),
        "--quiet",
    ])
    assert rc == 1, "Expected exit 1 when SXX-FAIL ids aren't mirrored."
