"""CI drift guard: every `SXX-FAIL` block in TEST_REPORT.md must be mirrored
as a `(#US-XX)` reference under `[Unreleased] → Fixed` in CHANGELOG.md.

Why: Phase 5 records failures in TEST_REPORT.md and Phase 6 ships fixes
mirrored as a `Fixed` bullet under `[Unreleased]` in CHANGELOG.md. Without
an automated check the two documents drift — a fix lands, the CHANGELOG
entry is forgotten, and downstream users miss the wire-protocol breaking
change.

Usage::

    python scripts/changelog_drift.py            # exit 0 if drift == 0
    # OR via pytest:
    pytest tests/test_changelog_drift.py -q       # same assertions via fixture

Returns ``0`` if all `SXX-FAIL` ids are mirrored, ``1`` otherwise with the
list of dropped ids on stderr.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEST_REPORT = ROOT / "TEST_REPORT.md"
DEFAULT_CHANGELOG = ROOT / "CHANGELOG.md"

# SXX-FAIL block heading in TEST_REPORT.md (Phase 5 schema). Captures
# the full id, e.g. `US-S05-FAIL`.
_FAIL_HEADING_RE = re.compile(
    r"^###\s+(?P<id>US-\w+-FAIL):", re.MULTILINE,
)

# Mirror reference in CHANGELOG.md — either `(US-XX)` or Markdown-link
# `[text](#US-XX)`. Convention: the `#US-XX` token must be the *only*
# content of its parenthetical, so prose like "(see #US-S05 issue thread)"
# is NOT treated as a fix.
_FIXED_REF_RE = re.compile(r"\(#?(?P<id>US-\w+)\)")

# Section boundaries.
_SECTION_HEADER_RE = re.compile(r"^##\s+(?P<title>[^\n]+)$", re.MULTILINE)
_H3_HEADER_RE = re.compile(r"^###\s+(?P<title>[^\n]+)$", re.MULTILINE)


def _normalise_newlines(text: str) -> str:
    """Collapse CRLF / CR to LF so section-boundary regexes are platform-stable.

    A Windows-driven editor that sneaks ``\\r\\n`` into TEST_REPORT or
    CHANGELOG would otherwise silently fail the section delimiter
    (``:^##\\s+\\[Unreleased\\]\\s*$\\n``) and report zero drift on a
    drifted repo.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def collect_fail_ids(test_report_text: str) -> list[str]:
    """All full `### US-XX-FAIL:` ids from TEST_REPORT.md, in document order."""
    return [m.group("id") for m in _FAIL_HEADING_RE.finditer(test_report_text)]


def collect_subsection(
    text: str, *, top_header: str, subsection: str
) -> str | None:
    """Return the body of `### subsection` under `## top_header` in `text`."""
    top = re.search(
        rf"^##\s+{re.escape(top_header)}\s*$\n(?P<body>.*?)(?=^##\s+|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if top is None:
        return None
    body = top.group("body")
    sub = re.search(
        rf"^###\s+{re.escape(subsection)}\s*$\n(?P<sbody>.*?)(?=^###\s+|\Z)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    return sub.group("sbody") if sub else None


def collect_fixed_ids(changelog_text: str) -> list[str]:
    """All `(#US-XX)` references under `[Unreleased] → Fixed`."""
    section = collect_subsection(
        changelog_text, top_header="[Unreleased]", subsection="Fixed",
    )
    if section is None:
        return []
    return [m.group("id") for m in _FIXED_REF_RE.finditer(section)]


def check_drift(
    test_report_path: Path = DEFAULT_TEST_REPORT,
    changelog_path: Path = DEFAULT_CHANGELOG,
) -> tuple[list[str], int]:
    """Return ``(missing_us_ids, fail_block_count)``.

    ``missing_us_ids`` is the list of SXX-FAIL ids NOT mirrored as a Fixed
    bullet. Empty means no drift. The comparison is
    ``stripped_fail_ids \\ fixed_ids`` — strip removes the trailing
    ``-FAIL`` so a `### US-S05-FAIL:` block matches a `(#US-S05)` Fixed
    reference.
    """
    test_report_text = _normalise_newlines(
        test_report_path.read_text(encoding="utf-8"),
    )
    changelog_text = _normalise_newlines(
        changelog_path.read_text(encoding="utf-8"),
    )
    fail_full = collect_fail_ids(test_report_text)
    fixed = set(collect_fixed_ids(changelog_text))
    fail_base = {f.replace("-FAIL", "") for f in fail_full}
    return sorted(fail_base - fixed), len(fail_full)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scripts.changelog_drift",
        description="Fail when TEST_REPORT.md SXX-FAIL blocks are not "
                    "mirrored as Fixed bullets in CHANGELOG.md.",
    )
    parser.add_argument("--test-report", type=Path, default=DEFAULT_TEST_REPORT)
    parser.add_argument("--changelog", type=Path, default=DEFAULT_CHANGELOG)
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress the OK message on a clean run.",
    )
    args = parser.parse_args(argv)

    if not args.test_report.is_file():
        print(
            f"error: TEST_REPORT not found at {args.test_report}",
            file=sys.stderr,
        )
        return 2
    if not args.changelog.is_file():
        print(
            f"error: CHANGELOG not found at {args.changelog}",
            file=sys.stderr,
        )
        return 2

    missing, fail_count = check_drift(args.test_report, args.changelog)
    if missing:
        print(
            "CHANGELOG drift: TEST_REPORT.md SXX-FAIL blocks not mirrored as "
            "Fixed bullets under `[Unreleased]`:",
            file=sys.stderr,
        )
        for user_story in missing:
            print(
                f"  - {user_story}  (need a `Fixed` bullet referencing it)",
                file=sys.stderr,
            )
        return 1
    if not args.quiet:
        print(
            f"OK: {fail_count} SXX-FAIL block(s) mirrored as Fixed bullets."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
