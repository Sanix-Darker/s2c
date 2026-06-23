# Changelog

All notable changes to `s2c` will be documented in this file.

The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **How this file stays accurate.** Every `SXX-FAIL` raised in
> `TEST_REPORT.md` becomes a bullet under `[Unreleased] → Fixed` in this
> file when Phase 6 merges the fix. Every wire-protocol or CLI breaking
> change (currently: NDJSON framing, asyncio migration, textual TUI) is
> flagged under `[Unreleased] → Changed` with a one-line migration note
> for downstream users.

---

## [Unreleased]

> Phase 6 fix log. As Phase 6 ships, append bullet points below; never
> edit a released section once it ships.

### Added

- _(none yet — Phase 6 entries will be appended below)_

### Changed

- _(none yet)_

### Fixed

- _(none yet — every `SXX-FAIL` from `TEST_REPORT.md` that gets fixed in
  Phase 6 lands here as a bullet, referencing the story ID with `(#US-XX)`)_

### Removed

- _(none yet)_

### Deprecated

- _(none yet)_

### Security

- _(none yet)_

#### Wire-protocol migration notes (for downstream users)

The wire protocol switched from "raw JSON over TCP" to
**newline-delimited JSON (NDJSON)** in version 0.0.7. Any client built
against the pre-0.0.7 protocol will trip
`MessageSizeExceededError` or fail `json.loads` because clients no longer
read exactly one JSON object per `recv()` call. The mandatory update is:

```python
from s2c.framing import Framer
framer = Framer()
for chunk in sock.recv(4096):
    for msg in framer.feed(chunk):
        handle(msg)
```

---

## [0.1.0] — Phase 1 (2026-06-23)

Re-release of `[0.0.7]` below — identical content, just a
version-pointer increment so the canonical Phase 1 anchor is the
`0.1.0` git tag instead of the previous `0.0.7` snapshot. See
`[0.0.7]` for the full Phase 1 release notes (NDJSON framing
migration, console-script fix, hardware-independent test suite,
idempotent peer bookkeeping, half-close disconnect, README honesty,
per-connection flicker removal, etc.).

**No code changes between `0.0.7` and `0.1.0`** — the version bump is
informational: it keeps the `git tag 0.1.0` pointer consistent with
this CHANGELOG entry for users cloning at the `0.1.0` tag, so the
on-disk top-level release notes line up with the named anchor.

---

## [0.0.7] — Phase 1 (2026-06-23)

Phase 1 ships correctness, packaging, and tests. The product is the
**same s2c you remember**; what changed underneath is enough that
upstream integrators should read the migration notes above.

### Added

- **NDJSON framing** via `s2c.framing.Framer`. The wire protocol is now
  newline-delimited JSON so partial or coalesced TCP segments no longer
  crash `json.loads`, and per-chunk throughput is fixed regardless of
  MTU choice. New helpers: `Framer.feed()`, `encode(obj)`,
  `encode_line(obj)`. (#US-S05, #US-C07, #US-C08)
- **`s2c` console-script entry** ships out of the box. `pip install s2c`
  followed by `s2c --help` works; the previous release's entry pointed
  to a non-existent `s2c.main` module and the command literally did not
  exist on disk. (#US-PKG01)
- **Hardware-independent test suite** — `pytest tests/` is green end-to-end
  on a clean machine with no camera or microphone. Tests live in
  `tests/test_framing.py` (adversarial NDJSON cases),
  `tests/test_server.py` (real socketpair + ephemeral-port integration),
  and `tests/test_client.py` (Client tests via `pytest-mock`). (#US-T01,
  #US-T02, #US-T03)
- **Synthetic baseline benchmark** at `benchmarks/profile.py`. Five
  scenarios (`framing`, `ascii`, `audio-encode`, `server-fanout`,
  `client-loop`) capture FPS / CPU% / packets-per-second on today's
  codebase so Phase 2 wins are quantifiable. Snapshot of the run on
  this commit lives in `benchmarks/baselines/before-phase2.json`.
- **Logger-driven observability** — `Server` and `Client` route every
  error through stdlib `logging`, formatted with timestamps and
  `[levelname] name: msg`. Verbosity scales with `-v` / `-vv` on the
  CLI. Pre-0.0.7 errors were `print(excp)` with no traceback. (#US-S07)

### Changed

- **`Client.__init__` is configuration-only.** It used to open the
  socket, the camera, and the mic immediately. `run()` is the new
  seam that performs all of those side effects. This is the test seam
  that lets `tests/test_client.py` build a `Client` without a
  webcam. (#US-C01)
- **`Server` lifecycle is now testable.** `Server.shutdown(timeout)`
  drains listening socket + every peer connection + every per-conn
  worker thread deterministically. Used by `Server` SIGINT handler
  AND every `tests/test_server.py` fixture teardown.
- **Idempotent peer bookkeeping.** `_remove_peer`,
  `_find_and_remove`, `_broadcast`'s send-failure path, and the
  per-connection worker thread (`_spawn_handler` → `_handle_runner`)
  are all re-entrancy safe under their respective locks, so a dead
  peer no longer accumulates in `Server.rooms`.
- **Half-close on disconnect.** Every `conn.close()` is preceded by
  `conn.shutdown(SHUT_WR)` so the peer observes a clean `FIN`
  (`recv() == b""`) instead of an `RST` (`ECONNRESET`).
- **`pyproject.toml` declares a `[project.scripts]` table** that points
  `s2c` and `s2c_server` at `s2c.__main__:main` and
  `server.main:main` respectively. Previously the `s2c` entry pointed
  to a non-shipped module and the CLI shipped broken.

### Fixed

- **TCP framing crash on partial/coalesced segments** (server #US-S05
  and client #US-C07): one `json.loads` per `recv(4096)`. Crashed on
  any payload larger than the recv buffer or any two messages
  arriving in the same segment. Now handled by `Framer.feed()`
  incrementing through the segment boundary.
- **Hang on graceful peer close** (client #US-C08): `_recv_data`
  used `while True: recv(4096)` and treated `b""` as a fatal error.
  Now breaks out cleanly and lets `_dispatch_chunk` finish any frames
  already inside the framer.
- **Dead-peer memory leak** (server #US-S03 follow-up): `Server.rooms`
  accumulated zombie entries because `_save_room` never had a
  matching `_remove_peer`. Phased cleanup: peer removal on
  recv-failure, on graceful close, and on `Server.shutdown()`.
- **Console-script dead link** (#US-PKG01): `pip install s2c`
  installed a `s2c` command that immediately failed because the
  configured entry module did not exist. Now points to a real shipped
  function.
- **README honesty** (#US-X01): the headline no longer claims PGP/AES
  encryption the codebase never implemented. It now reads
  "_encryption support is planned for a future release_".
- **Per-connection `os.system('clear')` flicker** (foundation for
  #US-C16): pre-0.0.7 called `os.system("clear")` from a 20 Hz render
  loop, nuking scrollback. Replacement is the textual widget tree
  in Phase 3.

### Removed

- `tests/test_camera.py` (commented-out, hardware-dependent). Replaced
  by `tests/test_client.py` with `pytest-mock` injections. No
  behaviour change for users, but CI no longer skips silently.

### Security

- None.

---

## [0.0.6]

No schema-stable changelog yet — see git history for the diff.
