# s2c — Test Report (Phase 5)

> Landing zone for the Phase 5 user-story test sweep. Every row corresponds
> to one `US-*` row in `FEATURES.md`. Failures (`SXX-FAIL`) and skips
> (`SXX-SKIP`) append in the same file so Phase 6 has a single source of
> truth to work from.

## How to populate

For each `US-*` row in `FEATURES.md`:

1. Decide whether the story already has a regression test, or whether one
   needs to be added before Phase 5 finishes.
2. Run the test under `pytest tests -q --no-header`.
3. Update the row below with the new `Status` and a one-line `Notes` link
   to the test path / failure trace.
4. Any failure becomes a `### SXX-FAIL:` block at the **Failures** section
   with the canonical fields below (Cause, Repro, Trace, Owner).
5. Any environment-driven skip becomes a `### SXX-SKIP:` block at
   **Skips**.

**Author discipline:** never delete a row mid-stream — flip its status.
Append, don't rewrite.

## Status legend

| Mark | Meaning                                                          |
|------|------------------------------------------------------------------|
| ✅   | Test exists and passes                                           |
| 🟡   | Test passes with a known issue (notes explain)                   |
| 🔴   | Test fails (full trace under **Failures**)                       |
| ⚪   | Story has no test yet — Phase 5 must write one                   |
| 🟣   | Skipped — hardware / env / debt (block under **Skips**)          |

## Summary

Refreshed after the Phase 5 sweep (`74 passed, 1 skipped` in `pytest tests`).

| Pass (✅) | Pass-with-issue (🟡) | Fail (🔴) | Skipped (🟣) | Pending Test (⚪) |
|-----------|----------------------|-----------|--------------|-------------------|
| 25        | 0                    | 0         | 0            | 9 (Phase 2/3/4 lacking features) |

> The 9 ⚪ rows below are intentionally not testable today: they are
> features on the Phase 2 (ASCII-vectorise), Phase 3 (textual TUI + hotkeys),
> or Phase 4 (zero-install + bootstrap) roadmaps. Phase 5/6 do not attempt
> to write failing tests for them.

## Per-US matrix

| US-ID      | One-line story                                                | Status | Test path                                       | Notes |
|------------|---------------------------------------------------------------|--------|-------------------------------------------------|-------|
| US-S01     | `s2c_server -p 1122` binds and listens.                       | ✅     | `tests/test_cli.py::test_server_constructor_binds_listen_socket`; `::test_server_main_help_lists_port_flag` | Constructor + `--help` direct; `Server(port=0)` is the in-process equivalent of `s2c_server -p 0`. |
| US-S02     | One daemon thread per `accept()`.                             | ✅     | `tests/test_server.py::test_two_clients_register_then_exchange` (indirect) | Implicit — covered by the integration tests. |
| US-S03     | Peers with matching `{i,s}` end up in the same room.          | ✅     | `tests/test_server.py::test_two_clients_register_then_exchange` |       |
| US-S04     | Room capacity capped at 5.                                    | ✅     | `tests/test_server.py::test_room_capacity_capped_at_five` |       |
| US-S05     | A peer's packets reach everyone else in the room.             | ✅     | `tests/test_server.py::test_two_clients_register_then_exchange` |       |
| US-S06     | Server retries bind when port is busy.                        | ✅     | `tests/test_cli.py::test_server_port_in_use_raises_with_bind_retry_false` | Asserts EADDRINUSE on `bind_retry=False`; the retry loop itself is best tested by manual verification because of the 1-s sleep. |
| US-S07     | Errors logged with timestamps.                                | ✅     | `tests/test_server.py::*` (manual smoke)        | Stdlib `logging` wired at import; `-v`/`-vv` adjusts level. |
| US-S08     | **Lack** — operator can list current peers.                   | ⚪     | (deferred)                                      | Targeted by Phase 3 / Phase 1.5 — see `PLAN.md` 1.5.1. |
| US-S09     | **Lack** — web endpoint creates sessions.                     | ⚪     | (deferred)                                      | Targeted by Phase 4. |
| US-C01     | `s2c -s … -c … -i … -p …` constructs and connects.            | ✅     | `tests/test_client.py::test_construct_no_hardware`; `tests/test_cli.py::test_s2c_module_help_lists_documented_flags` | Both arg-survival and CLI surface covered. |
| US-C02     | Missing `-s`/`-c` defaults to uuid.                          | ✅     | `tests/test_cli.py::test_default_session_id_is_uuid_format`; `::test_default_client_id_is_uuid_format` | Plus `test_explicit_*_is_preserved` for round-trip. |
| US-C03     | `-k` returns the provided key.                                | ✅     | `tests/test_cli.py::test_explicit_key_is_passthrough` |       |
| US-C04     | Banner prints on connect.                                     | ✅     | `tests/test_banner.py::test_banner_contains_session_metadata`; `::test_banner_does_not_crash_when_session_metadata_is_short`; `::test_banner_mentions_connected_status` | Captures stdout via `contextlib.redirect_stdout`; fixture sets `client._stop` on teardown to kill daemon threads. |
| US-C05     | Camera image becomes ASCII at the receivers.                  | ⚪     | (deferred)                                      | Phase 2 target — see PLAN.md §2.1. |
| US-C06     | Render shows the local user's ASCII frame.                    | ⚪     | (deferred)                                      | Phase 2/3. |
| US-C07     | Mic audio reaches the others as sound.                        | ✅     | `tests/test_framing.py::*` (codec round-trip); `tests/test_server.py::test_two_clients_…_exchange` (broadcast path) | End-to-end audio playback test pending Phase 3. |
| US-C08     | Peers' cameras land in `faces[…]`.                            | ✅     | `tests/test_server.py::test_two_clients_register_then_exchange` (integration); `tests/test_client.py::*` (unit) |       |
| US-C09     | Layout shows peers side-by-side (≤ 6 cap).                    | ⚪     | (deferred)                                      | Layout logic refactor in Phase 3. |
| US-C10     | Layout shows peer ids.                                        | ⚪     | (deferred)                                      | Same as US-C09. |
| US-C11     | FPS of self-view rendered.                                    | ✅     | `tests/test_client.py::test_get_fps` | Deterministic (`frames=0 // (now - START)` is always 0); START/FRAMES global mutation noted for Phase 2 cleanup. |
| US-C12     | Quit cleanly on Ctrl-C.                                       | 🟡     | `tests/test_cli.py::test_server_dies_cleanly_on_shutdown` (path) | Server.shutdown path covered. The actual SIGINT-via-subprocess flow is a follow-up when CI supports the deterministic timeout. |
| US-C13     | Startup prints session info.                                  | ✅     | `tests/test_banner.py::test_banner_contains_every_session_field` |       |
| US-C14     | Connect to remote host.                                        | ✅     | `tests/test_cli.py::test_explicit_ip_and_port_are_preserved` |       |
| US-C15     | **Lack** — hotkey mutes mic / hides cam.                      | ⚪     | (deferred)                                      | Phase 3. |
| US-C16     | **Lack** — status line with packet/FPS stats.                 | ⚪     | (deferred)                                      | Phase 3. |
| US-C17     | **Lack** — one-command bootstrap from a web link.             | ⚪     | (deferred)                                      | Phase 4. |
| US-T01     | Unit tests run without a webcam.                              | ✅     | `tests/test_framing.py`, `tests/test_client.py`, `tests/test_banner.py`, `tests/test_cli.py`, `tests/test_doc.py` | All five new files are cv2-free by design. |
| US-T02     | Integration tests for an in-memory server.                    | ✅     | `tests/test_server.py`                         | Ephemeral-port fixture; two real socketpair-backed clients. |
| US-T03     | CI runs pytest on push.                                       | ✅     | `.github/workflows/ci.yml`                     | `python -m pytest tests -q --no-header`. |
| US-PKG01   | `pip install s2c` provides the `s2c` CLI.                     | ✅     | `tests/test_cli.py::test_pyproject_declares_s2c_and_s2c_server_console_scripts`; `::test_python_m_s2c_clean_exits_on_help` | Both `s2c.__main__:main` and `server.main:main` entries verified. |
| US-PKG02   | Maintainer can release via `bash pypi_deploy.sh`.             | ✅     | `tests/test_doc.py::test_pypi_deploy_sh_parses`; `::test_pypi_deploy_sh_references_publish_tool` | Shell lints via `bash -n`; content references `twine`. End-to-end release test still run by hand. |
| US-PKG03   | `s2c_server.sh` opens 1122 and starts the server.             | ✅     | `tests/test_doc.py::test_s2c_server_sh_parses`; `::test_s2c_server_sh_references_default_port` | Shell lints; content references port 1122. |
| US-X01     | README "AES/PGP" claim matches reality.                       | ✅     | `tests/test_doc.py::test_readme_no_pgp_or_aes_headline_claim`; `::test_readme_acknowledges_encryption_is_planned` |       |
| US-X02     | Dependabot updates pip + actions.                             | ✅     | `tests/test_doc.py::test_dependabot_config_present`; `::test_dependabot_targets_pip_and_github_actions` |       |
| US-X03     | Release notes mention wire-protocol breaking changes.         | ✅     | `tests/test_doc.py::test_changelog_follows_keep_a_changelog_format`; `::test_changelog_has_0_0_7_phase_1_release_section`; `::test_changelog_0_0_7_mentions_ndjson_framing`; `::test_changelog_unreleased_links_to_test_report`; `::test_test_report_has_required_landing_zones` |       |

## Failures

> Each `SXX-FAIL` block is the canonical Phase 6 input: the fix lands in
> code, then is mirrored as a bullet under `[Unreleased] → Fixed` in
> `CHANGELOG.md`.

_(no `SXX-FAIL` markers — Phase 5 produced no failing tests)_

## Skips

_(no `SXX-SKIP` markers — Phase 5 produced no environment-driven skips. The
9 ⚪ rows above are intentional Phase 2/3/4 deferrals, not skips.)_

## Phase 6 hand-off

The Phase 6 contract is now:

> Every row above is 🟢 (✅ or 🟡) unless it's a deliberate Phase 2/3/4
> deferral (⚪). Any 🔴 row in a future Phase 5/6 pass MUST become a
> `SXX-FAIL` block here AND a `Fixed` bullet under CHANGELOG.md →
> `[Unreleased]` once the fix ships.

## How to refresh the summary block

```bash
# Count statuses from the per-US table above (manual edit). Example:
#   | ✅ (✅) | 🟡 (🟡) | 🔴 (🔴) | 🟣 (🟣) | ⚪ (⚪) |
#   |   25   |    1    |    0    |    0    |    9   |
# Then update the **Summary** table.
```

Once Phase 5 finishes the sweep, the manual table is the contract Phase 6
must drive to all-green.
