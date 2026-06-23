# s2c — Plan

> Source of questions answered by this plan: the audit in `FEATURES.md`, the thinker-with-files-gemini analysis, and the user's stated goals (extremely fast backend + TUI; a zero-install web session link; enhanced TUI; user-story-driven test/fix loop).

## Mission

Ship a s2c that is:
1. **Correct** — survives real-world TCP, real networks, real terminals without flicker or crash.
2. **Fast** — 15–25 fps on a low-end terminal, audio under 0.5 CPU core while sending.
3. **Zero-install** — a user clicks a link on `s2c.dev/new`, picks a room name, copies one command, pastes it anywhere, and is connected within 30 s with no `pip install` step.
4. **Observable** — every behaviour a user cares about is documented as a user story with a passing test.

## Phasing

Each phase ends with the **green** flip in `FEATURES.md` (status moves to 🟡/✅).

---

### Phase 0 — Bootstrap plan (this PR)

- [x] Audit & write `FEATURES.md` (user stories + status spreadsheet).
- [x] Write `PLAN.md` (this file).
- [x] Decide TUI library and zero-install architecture with the user — **chosen: textual + web app + bootstrap** (see "Locked architectural decisions").

---

### Phase 1 — Correctness, packaging & tests ✅ COMPLETE

> Fix every 🔴 row in `FEATURES.md`. Goal: nothing in the codebase surprises a new user.

**1.1 Packaging** ✅
- 1.1.1 ✅ `pyproject.toml [project.scripts]` now routes `s2c` to a real shipped entry `s2c.__main__:main`; the broken reference to the non-existent `s2c.main:main` is gone. `s2c_server` continues to work.
- 1.1.2 ✅ `Client.__init__` is now a pure constructor (no camera/mic open); `Client.run()` is the seam that does setup + threads. Tests can build a `Client` without hardware.
- 1.1.3 ✅ `tests/conftest.py` adds `client/` and `server/` to `sys.path` so `pytest` finds them without any `pyproject` gymnastics.

**1.2 Streaming / framing** ✅
- 1.2.1 ✅ NDJSON protocol: every outbound payload in `server/main.py` and `client/main.py` uses `s2c.framing.encode_line(obj)` which appends `\n`.
- 1.2.1b ✅ New `s2c/framing.py` ships `Framer` (stateful accumulator + `MessageSizeExceededError` + malformed-skip recovery) plus `encode(obj)` / `encode_line(obj)` helpers used by both sides.
- 1.2.2 ✅ Server `_handle_client` and client `_recv_data` now drive `Framer.feed(chunk)` on every recv iteration — partial or coalesced frames no longer crash `json.loads`.
- 1.2.3 ✅ Empty `recv` is treated as peer-close: `_find_and_remove(conn)` then half-close (`shutdown(SHUT_WR)`) + `close()`, peer sees a clean FIN.
- 1.2.4 ✅ `_save_peer` / `_remove_peer` / `_find_and_remove` are idempotent under `self.lock`; `_spawn_handler` tracks worker Threads under `_workers_lock` and uses `threading.current_thread()` for canonical cleanup.

**1.3 Tests** ✅
- 1.3.1 ✅ `tests/test_camera.py` (commented out, hardware-dependent) is **deleted**; superseded by `tests/test_client.py`.
- 1.3.2 ✅ `tests/test_framing.py` covers: split short line, partial-then-completion across two feeds, multi-line in one feed, malformed-is-skipped, oversize waits for the delimiter, oversize partial resets after raise, encode_line round-trip, protocol guards.
- 1.3.3 ✅ `tests/test_server.py` covers: ephemeral bind, two clients register + exchange, partial-frame completion, malformed skip, dead-peer removal, capacity cap (5), oversized partial FIN-closes the conn without leaking to neighbours, clean shutdown drains rooms.
- 1.3.4 ✅ `.github/workflows/ci.yml` runs `python -m pytest tests -q --no-header` on every push.

**1.4 Crypto (README honesty)** ✅
- 1.4.1 ✅ README headline no longer claims PGP/AES — says "encryption support is planned for a future release".
- 1.4.2 ✅ `s2c/cli_args.py` keeps `-k` as a placeholder flag so the future migration to real crypto doesn't break user scripts.

**Status at end of Phase 1**
- `pytest tests -q --no-header` → **42 passed, 1 skipped, 0 failures** in 6.25 s (no camera/mic touched).
- Pytest result: green.
- Code-reviewer: zero critical findings in the final pass.
- Next phase: **Phase 1.5 — asyncio migration** (required prerequisite for Phase 3 textual TUI).

---

### Phase 2 — Performance (drastic, aggressive)

> All work grounded in profiling the real hot paths. Goal: 15 fps on a Raspberry Pi without touching config.

**2.1 Vectorized ASCII**
- 2.1.1 Replace nested Python loop in `ascii_it` with `np.searchsorted(brightnesses, gray.ravel())` then `''.join(CHARACTERS[indices])`.
- 2.1.2 Build the multi-line string with `'\n'.join(rowstrings)`.
- 2.1.3 Pre-compute `INDICES` once per client (or once globally) using the actual image luminance histogram, not brute `for c in range(...)`.

**2.2 Frame rate & network throttling**
- 2.2.1 Add a `target_fps` config (default 15) enforced by a monotonic-clock cap on `_send_frames` AND `_render_faces`.
- 2.2.2 Skip a frame if the previous `sendall` is still pending; use `MSG_DONTWAIT` semantics via select().
- 2.2.3 Reduce outbound audio chunk size from 4096 to a smaller bind-friendly size; consider Opus if the dep budget allows (defer).

**2.3 Server**
- 2.3.1 Broadcast the **raw bytes** received (after the `\n`) to every other peer in the room. No re-serialization.
- 2.3.2 Replace the per-connection `Thread` with a single-threaded `selectors`-driven loop. Wire N rooms of 5 peers each in one Python process.
- 2.3.3 Add an exponential backoff on `connect_ex`, capped at 30 s.
- 2.3.4 Add a graceful shutdown: SIGINT/SIGTERM closes all sockets and joins workers.

**2.4 Stream-friendly render**
- 2.4.1 Move rendering to a single `rich.live.Live` over a `rich.layout.Layout` (preferred dependency) OR craft an ANSI diff-aware redraw in pure Python if `rich` is rejected.
- 2.4.2 End-of-output positioning: never call `os.system('clear')` (it nukes scrollback).
- 2.4.3 Render at most every 1/15 s, **not on every frame received** — render is decoupled from inbound frame rate.

---

### Phase 3 — TUI 2.0 (textual)

> Resolves US-C15, US-C16 and turns `_render_faces` into something users want to demo.

**3.1 App shell**
- 3.1.1 `S2CApp(textual.App)` with 3 vertical zones:
  - **Header**: room id, your client id, your truncated session key, peer count, live FPS, pkts/sec, mute/cam badges.
  - **Body** (`Grid`): one `PeerCard` widget per active peer (the local user is also a `PeerCard` with a "you" badge).
  - **Footer**: hotkey hints (`q` quit, `m` mute, `v` hide cam, `+/-` fps, `d` debug overlay).
- 3.1.2 CSS layout: when `len(peers) == 1` → 1×1; 2 → 1×2; 3-4 → 2×2; 5-9 → 3×3; 10+ → 4-row scrolling grid.
- 3.1.3 Debug overlay (`d`): floating `RichLog` window displaying the last 200 inbound NDJSON envelopes, gated behind a hidden flag in releases.

**3.2 Hotkeys**
- 3.2.1 `m` toggles `is_muted`. `action_toggle_mute()` flips the reactive; `_send_audio` reads it under a `threading.Lock` so the audio thread notices within 1 chunk.
- 3.2.2 `v` toggles `camera_enabled`. When off, `_send_frames` skips `cam.read()` and sends a 4-line "hidden" placeholder at 1 Hz so the UI still proves liveness.
- 3.2.3 `q` (and `Ctrl-C`) → `action_quit()`: signal media workers, flushes pending packets, awaits stream close, exits.
- 3.2.4 `+/-` → bumps `target_fps` in `[5, 10, 15, 20, 30]`; updates the Footer readout.

**3.3 PeerCard widget**
- 3.3.1 Each `PeerCard` keeps `reactive ascii_frame: str = ""`; `watch_ascii_frame` triggers a `Static.update()` (no full re-layout).
- 3.3.2 When `active_speaker == self.client_id`, the card paints a colored border via Textual CSS class hook (`speaking` toggled in `watch_active_speaker`).
- 3.3.3 ASCII converter in textual mode uses `rich.text.Text` with `style="bold"` on the speaker cell to make it pop in terminals that support ANSI.

---

---

### Phase 4 — Zero-install session link (web app + bootstrap combo)

> Primary deliverable for "from a link online web app running to create/generate a session." The web layer runs on the same asyncio loop as the chat server (Phase 1.5.1).

**4.1 Web session creator** (asyncio, shares loop with chat server)
- 4.1.1 Add `server/web.py` exposing `/`, `/new`, `/u/<room>`, `/join/<room>` via `aiohttp.web.Application` (new dep; chaise-lounge alternative is stdlib `http.server` if dep budget is tight). Bind a separate `--web-port` (default 8080) via `asyncio.gather(chat_server_task, web_app_task)`.
- 4.1.2 `/` renders an HTML landing page (jinja-free, just an f-string template) with: room name input, your display name, copy-paste button.
- 4.1.3 `/new` (POST) registers a session with `Server.handle_new_session(room)`, mints a short-lived `client_id` placeholder, and returns a redirect to `/u/<room>`.
- 4.1.4 `/u/<room>` lands on the live room page; shows peer list and another copy-paste button.

**4.2 Bootstrap one-liner**
- 4.2.1 Generate a `join.py` that:
   - determines `sys.executable` and `pip` (or `pipx` if present)
   - does `pip install --user s2c==<client_version>` only if importable `s2c` is missing or too old
   - `subprocess.run(['s2c', '-s', room, '-c', uuid, '-i', host, '-p', str(port)], check=True)`
- 4.2.2 Serve `join.py` at `/join/<room>` as `text/x-python` so `curl https://s2c.dev/join/demo | python3 -` works.
- 4.2.3 Ensure the bootstrap script supports both Linux/macOS and Windows (`.exe` not needed; `py -3` as fallback).

**4.3 Server-side support**
- 4.3.1 Add `Server.handle_new_session(room: str) -> session_id` so the web layer can allocate rooms ahead of time.
- 4.3.2 Add an admin auth token (`--web-token`) gating `/new` to avoid random room squatting.

**4.4 README + landing**
- 4.4.1 Replace the "Install bindings / pip install s2c" section with a "Click here, copy, paste" flow.
- 4.4.2 Record a 30-second demo gif to replace `/demo.gif`.

---

### Phase 5 — Test loop (user-story coverage)

> After Phase 1-4 status flips, run a one-test-per-US sweep.

For each `US-*` row in `FEATURES.md`:
- 5.1 ✅ status: confirm test exists and passes.
- 5.2 🟡 status: confirm regression test covers the fix.
- 5.3 🔴 → 🟡/✅ status: write the test that would have caught the bug, ensure it now passes.
- 5.4 ⚪ → 🟡 status: write the test alongside the new feature.

Document any failures in `TEST_REPORT.md` (`SXX-FAIL: <cause>`) and re-route to **Phase 6**.

---

### Phase 6 — Fix loop (logistical & UX errors)

> All `SXX-FAIL` items in `TEST_REPORT.md` must be addressed before exiting this phase:
- 6.1 Categorize: wire / runtime / UX / cosmetic.
- 6.2 For each: make the fix, append to `CHANGELOG.md`, re-run the corresponding Phase 5 test.

---

### Phase 7 — Re-test loop

> Full re-run after fixes:
- 7.1 Re-execute `pytest tests -v`.
- 7.2 Spin up the server, run the bootstrap on a clean VM, connect two clients, verify TUI 2.0 hotkeys end-to-end.
- 7.3 Flip any ✅ whose regression surfaced back to 🟡 and re-enter Phase 6.

---

## Locked architectural decisions (confirmed by user)

| # | Decision | Choice | Driver |
|---|----------|--------|--------|
| A1 | **TUI library** | **`textual`** (full async widget framework) | User explicit choice. Implies asyncio migration of the client. |
| A2 | **Zero-install UX** | **Web app + bootstrap combo** | User explicit choice. `server/web.py` (asyncio, shares the event loop with the chat server) exposes `/`, `/new`, `/u/<room>`, `/join/<room>`. Bootstrap is `curl .../join/<room> \| python3 -` — runs `pip install --user s2c` if needed, then launches the client. SSH-via-paramiko rejected (remote execution cannot reach local mic/cam). |

> All other decisions in this plan are derived from the two above plus the audit in `FEATURES.md`.

---

## Phase 1.5 — Asyncio migration (prerequisites for Phases 2-4)

> Required because textual demands an event loop, and the server benefits from sharing that loop with the web layer. Phase 1's tests MUST stay green before this phase.

**1.5.1 Server — asyncio**
- Replace `Thread(target=_handle_client)` per connection with `asyncio.start_server(...)` driving a single async NDJSON framer.
- Re-broadcast the **raw received bytes** (after the `\n`) to every other peer in the same room via a per-room `set[StreamWriter]` tracked in `dict[str, set[StreamWriter]]` guarded by an `asyncio.Lock`.
- Replace ad-hoc `print` logging with `logging` + `--verbose`.
- Graceful shutdown: SIGINT/SIGTERM cancels all tasks, drains writers, closes the socket.

**1.5.2 Client — textual + worker threads for blocking media**
- Top-level `S2CApp(textual.App)` owns:
  - the asyncio event loop driving network I/O (`asyncio.open_connection` + NDJSON framer);
  - media workers (`send_audio`, `send_frames`) launched as `@work(thread=True)` so PyAudio/OpenCV stay synchronous and produce audio/video into `asyncio.Queue`s via `loop.call_soon_threadsafe`.
- Seams for testing:
  - `MediaSource` Protocol with `OpenCVMediaSource` and `DummyMediaSource` implementations;
  - `AudioSource` Protocol with `PyAudioMicSource` and `DummyAudioSource`;
  - `AudioSink` Protocol with `PyAudioSpeakerSink` and `DummyAudioSink`.
- Quit path: `action_quit()` sets a `threading.Event`, joins media workers, awaits stream close, drains queues.

**1.5.3 Reactive state surface** (drives Phase 3 widgets):

| Reactive attribute        | Type                       | Drives                                                              |
|---------------------------|----------------------------|---------------------------------------------------------------------|
| `peers`                   | `reactive[set[str]]`       | `Grid` peer-card mount/unmount via `watch_peers` diff               |
| `is_muted`                | `reactive[bool]`           | Footer mute indicator; `_send_audio` early-exits when muted         |
| `camera_enabled`          | `reactive[bool]`           | Footer indicator; `_send_frames` skips `cam.read()` when off        |
| `fps_out`                 | `reactive[int]`            | Header/StatusBar telemetry; updated by a 1 Hz `set_interval`        |
| `pkts_in_last_sec`        | `reactive[int]`            | Header/StatusBar telemetry                                          |
| `net_status`              | `reactive[str]`            | Header style: "Connected" / "Reconnecting" / "Offline"              |
| `active_speaker`          | `reactive[str \| None]`    | Computed from per-frame RMS; highlights the speaker's `PeerCard`    |

**1.5.4 Test seams**
- `MediaSource`/`AudioSource`/`AudioSink` Protocols above — `Dummy*` impls ship in `client/dummy.py`.
- Tests construct `S2CApp.build(session=..., media=DummyMediaSource(), audio=DummyAudioSource(), sink=DummyAudioSink())` — no camera/mic needed.
- A separate `@pytest.mark.hardware` class exercises the real `OpenCVMediaSource` / `PyAudioMicSource` / `PyAudioSpeakerSink` against the dummy counterparts so CI never opens hardware.

---
