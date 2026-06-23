# s2c — benchmarks

The Phase 1 deliverable is correct but not yet fast. Before Phase 2 starts
optimising, we record a deterministic baseline so every Phase 2 commit can
quote numbers ("FPS went from 12 → 38") instead of vibes.

## Usage

```bash
# run all scenarios with synthetic (camera-free, mic-free) inputs
python -m benchmarks.profile

# capture a named baseline snapshot into benchmarks/baselines/
python -m benchmarks.profile --out benchmarks/baselines/before-phase2.json \
                              --label before-phase2

# a single scenario (fast feedback loop)
python -m benchmarks.profile --scenario ascii --trials 10 --iterations 2000

# opt-in to real hardware (skipped automatically if no camera / mic)
python -m benchmarks.profile --with-camera
```

`python3 benchmarks/profile.py` works equivalently.

## Scenarios

| Scenario          | What it measures                                                         | Default iters |
|-------------------|--------------------------------------------------------------------------|---------------|
| `framing`         | `Framer.feed()` + `encode_line()` round-trip on N NDJSON lines           | 5000          |
| `ascii`           | `Client.ascii_it()` on a synthetic BGR frame (the perf headline)         | 1000          |
| `audio-encode`    | base64 + json.dumps + `encode_line()` per audio chunk (no socket send)   | 5000          |
| `server-fanout`   | 3 in-room peers; one broadcasts, others receive; broadcasts/sec          | 500           |
| `client-loop`     | `Client._send_now()` → in-process socketpair → drains                    | 5000          |
| `all`             | Runs every scenario above in sequence                                    | —             |

## Output schema

JSON to stdout (and `benchmarks/results.json` by default), shaped as:

```json
{
  "python": "3.12.x",
  "platform": "linux",
  "git_describe": "v0.0.7-5-gabcd",
  "label": "before-phase2",
  "scenario_results": [
    {
      "scenario": "ascii",
      "trials": 5,
      "iterations_per_trial": 1000,
      "wall_seconds_mean": 0.83,
      "wall_seconds_stdev": 0.02,
      "process_seconds_mean": 0.79,
      "cpu_pct_mean": 95.2,
      "frames_per_sec_mean": 1204.8
    }
  ]
}
```

`*-mean` and `*-stdev` are aggregated across `--trials`. CPU% is
`process_time_delta / wall_time_delta * 100` — close to 100% for
pure-Python loops, lower when GIL is released (socket sendall,
base64 in C, json encoder via C extension).

## Why not just measure end-to-end FPS?

End-to-end FPS on a real webcam is hostage to the camera's own framerate,
the terminal size, the renderer's blink, and the user's cable. The Phase 2
optimisations target specific Python-level patterns (the `for c in range(...)`
pixel loop in `ascii_it`, the per-row `string += ...` concatenation in
`generate_frame`, the per-recipient `json.dumps` in `_broadcast`).
Per-pattern micro-benchmarks isolate each variable so the corresponding
Phase 2 commit can show a real percentage improvement instead of
"it feels snappier".

## Caveats

* **Every record carries a `"status"` field** — `"ok"`, `"skipped"`, or
  `"error"`. Consumers can default to `"ok"` for missing fields but the
  explicit string is friendlier in dashboards.
* `cpu_pct_mean` is **process-wide**, not thread-scoped. `time.process_time`
  sums CPU time across every OS thread in this Python process, so the
  `server-fanout` scenario (≈4 worker threads) legitimately shows numbers
  above 100%. Compare on the same machine, same load.
* The `ascii` scenario uses uniform random pixels (full 0–255 range) and
  therefore hits the worst case of `range(min, max)` in `ascii_it`. The
  `frames_per_sec_mean` is a **ceiling**, not a typical number — Phase 2
  should drive it sharply upward once the inner loops are vectorised.
