"""Synthetic baseline benchmark for s2c.

Captures current FPS / CPU% / packets-per-second across the hot paths in the
Phase 1 codebase so Phase 2 perf work has measurable wins to claim. Runs
WITHOUT a camera or microphone by default (synthetic numpy inputs).
Use ``--with-camera`` to opt in to a real webcam if one is attached.

Usage::

    python -m benchmarks.profile                          # all scenarios
    python -m benchmarks.profile --scenario ascii --trials 10
    python -m benchmarks.profile --with-camera
    python -m benchmarks.profile --out baselines/before-phase2.json \\
                                  --label before-phase2
"""

from __future__ import annotations

import argparse
import base64
import gc
import json
import logging
import platform
import socket
import statistics
import subprocess
import sys
import threading
import time
from typing import Callable

import numpy as np

from s2c.framing import Framer, encode_line
from client.main import Client
from server.main import Server

log = logging.getLogger("s2c.benchmark")


def _stdev_or_zero(values: list[float]) -> float:
    """`statistics.stdev` raises on <2 points; benchmarks want a number either way."""
    return round(statistics.stdev(values), 6) if len(values) >= 2 else 0.0


def _try_import_cv2():
    """Return a cv2 module or None if opencv-python isn't installed."""
    try:
        import cv2  # type: ignore
        return cv2
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _synthetic_frame(h: int = 60, w: int = 20) -> np.ndarray:
    """Random BGR frame that matches the shape ``cv2.VideoCapture.read()`` returns."""
    return np.random.randint(0, 256, (h, w, 3), dtype=np.uint8)


def _synthetic_audio_chunk(num_samples: int = 512) -> bytes:
    """Random int16 PCM chunk matching ``Client.CHUNK`` * 2 bytes per sample."""
    return np.random.randint(-32768, 32767, num_samples, dtype=np.int16).tobytes()


def _wait_until(predicate, *, timeout: float = 2.0, interval: float = 0.005) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _drain(sock: socket.socket, *, idle: float = 0.15) -> int:
    """Read whatever's available on `sock` for `idle` seconds. Return bytes read."""
    sock.setblocking(False)
    total = 0
    deadline = time.monotonic() + idle
    try:
        while time.monotonic() < deadline:
            try:
                chunk = sock.recv(65536)
            except BlockingIOError:
                time.sleep(0.005)
                continue
            except OSError:
                return total
            if not chunk:
                return total
            total += len(chunk)
    finally:
        sock.setblocking(True)
    return total


def _git_describe() -> str:
    try:
        return subprocess.check_output(
            ["git", "describe", "--always", "--dirty"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def _measure(work: Callable[[], None]) -> tuple[float, float]:
    """Run `work`; return (wall_seconds, process_seconds).

    GC is disabled across the trial to keep allocation-heavy scenarios
    (``audio-encode``, ``client-loop``) free of mid-trial GC pauses.
    """
    proc0 = time.process_time()
    wall0 = time.perf_counter()
    gc.disable()
    try:
        work()
    finally:
        gc.enable()
    return time.perf_counter() - wall0, time.process_time() - proc0


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------


def scenario_framing(*, trials: int, iterations: int) -> dict:
    """``Framer.feed()`` end-to-end on N pre-encoded NDJSON lines."""
    encoded = [
        encode_line({"i": f"peer{i}", "s": "lobby", "v": "X" * 64})
        for i in range(iterations)
    ]
    buf = b"".join(encoded)
    # Warmup
    _ = list(Framer().feed(buf))

    walls, procs = [], []
    for _ in range(trials):
        w, p = _measure(lambda: list(Framer().feed(buf)))
        walls.append(w); procs.append(p)
    wall_mean = statistics.mean(walls)
    proc_mean = statistics.mean(procs)
    return {
        "scenario": "framing",
        "status": "ok",
        "trials": trials,
        "iterations_per_trial": iterations,
        "wall_seconds_mean": round(wall_mean, 6),
        "wall_seconds_stdev": _stdev_or_zero(walls),
        "process_seconds_mean": round(proc_mean, 6),
        "cpu_pct_mean": round(100 * proc_mean / max(wall_mean, 1e-9), 2),
        "frames_per_sec_mean": round(iterations / max(wall_mean, 1e-9), 1),
    }


def scenario_audio_encode(*, trials: int, iterations: int) -> dict:
    """base64 + json.dumps + encode_line per chunk — no socket send."""
    chunk = _synthetic_audio_chunk(Client.CHUNK)
    sample_packet = encode_line({
        "i": "bench",
        "s": "bench-room",
        "a": base64.b64encode(chunk).decode(),
    })
    pkt_bytes = len(sample_packet)

    walls, procs = [], []
    for _ in range(trials):
        def work():
            payload_chunk = base64.b64encode(chunk).decode()
            for _ in range(iterations):
                encode_line({
                    "i": "bench", "s": "bench-room", "a": payload_chunk,
                })
        w, p = _measure(work)
        walls.append(w); procs.append(p)
    wall_mean = statistics.mean(walls)
    proc_mean = statistics.mean(procs)
    return {
        "scenario": "audio-encode",
        "status": "ok",
        "trials": trials,
        "iterations_per_trial": iterations,
        "bytes_per_packet": pkt_bytes,
        "wall_seconds_mean": round(wall_mean, 6),
        "wall_seconds_stdev": _stdev_or_zero(walls),
        "process_seconds_mean": round(proc_mean, 6),
        "cpu_pct_mean": round(100 * proc_mean / max(wall_mean, 1e-9), 2),
        "packets_per_sec_mean": round(iterations / max(wall_mean, 1e-9), 1),
    }


def scenario_ascii(*, trials: int, iterations: int, with_camera: bool) -> dict:
    """Drive ``Client.ascii_it`` against BGR frames; FPS = iterations/second.

    Skips gracefully when opencv-python isn't installed (no baseline FPS,
    just a ``skipped`` record) so a CI without cv2 can still capture the
    rest of the suite. The metric reflects INDICES-build cost per frame
    because ``INDICES`` is mutated in place — Phase 2's vectorisation
    should drive this number sharply upward.
    """
    cv2 = _try_import_cv2()
    if cv2 is None:
        return {
            "scenario": "ascii",
            "status": "skipped",
            "trials": 0,
            "iterations_per_trial": iterations,
            "reason": "opencv-python not installed; install with: pip install opencv-python",
        }

    client = Client({
        "session_key": "bench",
        "session_id": "bench-room",
        "client_id": "bench",
        "ip": "127.0.0.1",
        "port": 0,
    })
    # Reset the module-level FPS counters so warmups can't poison the metric.
    import client.main as cli_main
    cli_main.START = time.time()
    cli_main.FRAMES = 0

    cam = None
    if with_camera:
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            cam = cap
        else:
            cap.release()
            log.warning(
                "--with-camera requested but no camera available; "
                "falling back to synthetic frames",
            )
    use_cam = cam is not None

    try:
        # Warmup — first run pays the ~256-iteration INDICES build.
        for _ in range(min(max(iterations // 10, 5), 50)):
            client.ascii_it(_synthetic_frame())

        def next_frame():
            if use_cam:
                ok, fr = cam.read()  # type: ignore[union-attr]
                if ok:
                    return fr
            return _synthetic_frame()

        walls, procs = [], []
        for _ in range(trials):
            def work():
                for _ in range(iterations):
                    client.ascii_it(next_frame())
            w, p = _measure(work)
            walls.append(w); procs.append(p)
        wall_mean = statistics.mean(walls)
        proc_mean = statistics.mean(procs)
        return {
            "scenario": "ascii",
            "status": "ok",
            "trials": trials,
            "iterations_per_trial": iterations,
            "frame_source": "camera" if use_cam else "synthetic",
            "wall_seconds_mean": round(wall_mean, 6),
            "wall_seconds_stdev": _stdev_or_zero(walls),
            "process_seconds_mean": round(proc_mean, 6),
            "cpu_pct_mean": round(100 * proc_mean / max(wall_mean, 1e-9), 2),
            "frames_per_sec_mean": round(iterations / max(wall_mean, 1e-9), 1),
        }
    finally:
        if cam is not None:
            try:
                cam.release()
            except Exception:  # noqa: BLE001
                pass


def scenario_server_fanout(*, trials: int, iterations: int) -> dict:
    """3 peers in a single room; one broadcasts, others receive; broadcasts/sec."""
    walls_send, procs_send = [], []
    walls_recv, procs_recv = [], []
    loss_counts = []

    for trial in range(trials):
        srv = Server(port=0, bind_retry=False)
        th = threading.Thread(
            target=srv.serve_forever, daemon=True, name=f"bench-srv-{trial}",
        )
        th.start()
        sid = f"bench-room-{trial}"
        peers: dict[str, socket.socket] = {}
        try:
            for cid in ("alice", "bob", "cleo"):
                s = socket.socket()
                s.connect(("127.0.0.1", srv.port))
                peers[cid] = s
            for cid, s in peers.items():
                s.sendall(encode_line({"i": cid, "s": sid, "v": "_init_"}))
            assert _wait_until(
                lambda: all(cid in srv.rooms.get(sid, {}) for cid in peers),
                timeout=2.0,
            ), "peer registration timed out"
            for s in peers.values():
                _drain(s, idle=0.1)
            # Warm-up broadcast so the server's handler threads are hot.
            peers["alice"].sendall(
                encode_line({"i": "alice", "s": sid, "v": "warmup"}),
            )
            _drain(peers["bob"], idle=0.1)
            _drain(peers["cleo"], idle=0.1)

            # --- send phase -----------------------------------------------
            send_wall_start = time.perf_counter()
            send_proc_start = time.process_time()
            for i in range(iterations):
                peers["alice"].sendall(encode_line({
                    "i": "alice", "s": sid, "v": f"f{i:06d} " + "X" * 32,
                }))
            s_wall = time.perf_counter() - send_wall_start
            s_proc = time.process_time() - send_proc_start

            # --- recv phase (validation that fan-out actually worked) -----
            recv_wall_start = time.perf_counter()
            recv_proc_start = time.process_time()
            bob = peers["bob"]; cleo = peers["cleo"]
            bob_framer = Framer(); cleo_framer = Framer()
            bob_count = cleo_count = 0
            # Track dead peers so one peer's disconnect doesn't starve the
            # other (old `break` exited the inner for-loop silently so the
            # surviving peer never got polled again on this trial).
            dead: set[str] = set()
            bob.setblocking(False); cleo.setblocking(False)
            try:
                deadline = time.monotonic() + 5.0
                while (
                    bob_count < iterations or cleo_count < iterations
                ) and time.monotonic() < deadline and len(dead) < 2:
                    progressed = False
                    for label, sock, framer in (
                        ("bob", bob, bob_framer),
                        ("cleo", cleo, cleo_framer),
                    ):
                        if label in dead:
                            continue
                        try:
                            chunk = sock.recv(65536)
                        except BlockingIOError:
                            continue
                        except OSError as exc:
                            log.warning(
                                "fanout-recv: peer %s died (%s); "
                                "continuing with the surviving peer",
                                label, exc,
                            )
                            dead.add(label)
                            continue
                        if chunk:
                            progressed = True
                            for _ in framer.feed(chunk):
                                if label == "bob":
                                    bob_count += 1
                                else:
                                    cleo_count += 1
                        else:
                            # Empty recv = graceful FIN (e.g. server
                            # `_handle_client` half-close). Treat the same
                            # as OSError so the surviving peer keeps being
                            # polled instead of the loop hammering a
                            # never-going-to-return socket.
                            log.warning(
                                "fanout-recv: peer %s FIN-closed; "
                                "presuming it received its share",
                                label,
                            )
                            dead.add(label)
                    if not progressed:
                        time.sleep(0.001)
                    if bob_count >= iterations and cleo_count >= iterations:
                        break
            finally:
                bob.setblocking(True); cleo.setblocking(True)
            r_wall = time.perf_counter() - recv_wall_start
            r_proc = time.process_time() - recv_proc_start

            loss_counts.append((bob_count, cleo_count))
            walls_send.append(s_wall); procs_send.append(s_proc)
            walls_recv.append(r_wall); procs_recv.append(r_proc)
        finally:
            for s in list(peers.values()):
                try:
                    s.close()
                except OSError:
                    pass
            srv.shutdown(timeout=2.0)

    bad = sum(1 for b, c in loss_counts if b != iterations or c != iterations)
    if bad:
        log.warning(
            "server-fanout: %d/%d trials had frame loss — increase iterations "
            "or check the server's broadcast path",
            bad, trials,
        )

    s_wall = statistics.mean(walls_send)
    s_proc = statistics.mean(procs_send)
    r_wall = statistics.mean(walls_recv)
    r_proc = statistics.mean(procs_recv)
    return {
        "scenario": "server-fanout",
        "status": "ok",
        "trials": trials,
        "iterations_per_trial": iterations,
        "peers": 3,
        "send_wall_seconds_mean": round(s_wall, 6),
        "send_wall_seconds_stdev": _stdev_or_zero(walls_send),
        "send_process_seconds_mean": round(s_proc, 6),
        "send_cpu_pct_mean": round(100 * s_proc / max(s_wall, 1e-9), 2),
        "broadcasts_per_sec_mean": round(iterations / max(s_wall, 1e-9), 1),
        "recv_wall_seconds_mean": round(r_wall, 6),
        "recv_wall_seconds_stdev": _stdev_or_zero(walls_recv),
        "recv_process_seconds_mean": round(r_proc, 6),
        "recv_cpu_pct_mean": round(100 * r_proc / max(r_wall, 1e-9), 2),
        # Counter-intuitive check: did bob and cleo actually receive every
        # frame the server broadcast? Phase 2 must not regress this to 0.
        "received_loss_trials": bad,
    }


def scenario_client_loop(*, trials: int, iterations: int) -> dict:
    """Drive ``Client._send_now`` through an in-process socketpair.

    Linux Unix-domain socket pairs buffer ~256 KB before backpressure
    kicks in. To keep the metric measuring send-path cost (not
    backpressure), ``b`` is drained in-line every 256 iterations so the
    buffer stays near-empty throughout the trial. The metric is therefore
    best-case send throughput; an opposing realistic peer would manifest
    as backpressure on the wall-clock mean.
    """
    walls, procs = [], []
    for trial in range(trials):
        a, b = socket.socketpair()
        try:
            client = Client({
                "session_key": "bench",
                "session_id": "bench-room",
                "client_id": "bench",
                "ip": "127.0.0.1",
                "port": 0,
            })
            # Disable the camera warning log inside _send_now if anything ever
            # cascades: it never should here because we never open a camera.
            client.sock = a
            # Warmup + drain so the kernel socket buffer isn't empty.
            client._send_now({"i": "bench", "s": "bench-room", "v": "warmup"})
            _drain(b, idle=0.05)

            def work():
                for i in range(iterations):
                    client._send_now({
                        "i": "bench",
                        "s": "bench-room",
                        "v": f"f{i:05d} " + "X" * 32,
                    })
                    # Mid-loop drain keeps the recv buffer near-empty so
                    # we measure send-path cost, not kernel-buffer
                    # backpressure. 256 ≈ the typical Linux AF_UNIX
                    # sndbuf size in pages.
                    if i and i % 256 == 0:
                        _drain(b, idle=0.001)
            w, p = _measure(work)
            walls.append(w); procs.append(p)
            # Final drain so the next trial starts cold.
            _drain(b, idle=0.05)
        finally:
            try:
                a.close()
            except OSError:
                pass
            try:
                b.close()
            except OSError:
                pass
    wall_mean = statistics.mean(walls)
    proc_mean = statistics.mean(procs)
    return {
        "scenario": "client-loop",
        "status": "ok",
        "trials": trials,
        "iterations_per_trial": iterations,
        "wall_seconds_mean": round(wall_mean, 6),
        "wall_seconds_stdev": _stdev_or_zero(walls),
        "process_seconds_mean": round(proc_mean, 6),
        "cpu_pct_mean": round(100 * proc_mean / max(wall_mean, 1e-9), 2),
        "frames_per_sec_mean": round(iterations / max(wall_mean, 1e-9), 1),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


SCENARIOS: dict[str, Callable[..., dict]] = {
    "framing": scenario_framing,
    "ascii": scenario_ascii,
    "audio-encode": scenario_audio_encode,
    "server-fanout": scenario_server_fanout,
    "client-loop": scenario_client_loop,
}


def _run_scenario(name: str, *, trials: int, iterations: int, with_camera: bool) -> dict:
    fn = SCENARIOS[name]
    if name == "ascii":
        return fn(trials=trials, iterations=iterations, with_camera=with_camera)
    return fn(trials=trials, iterations=iterations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="benchmarks.profile",
        description="Synthetic baseline benchmark for s2c (Phase 1).",
    )
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS) + ["all"],
        default="all",
        help="Which scenario to run. Default: all (in order).",
    )
    parser.add_argument(
        "--trials", type=int, default=5,
        help="Number of trials per scenario (default: 5).",
    )
    parser.add_argument(
        "--iterations", type=int, default=1000,
        help="Iterations per trial (default: 1000).",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Seed for numpy RNG so synthetic inputs are reproducible.",
    )
    parser.add_argument(
        "--with-camera", action="store_true",
        help="Try to open the webcam for the `ascii` scenario; falls back to "
             "synthetic frames if no camera is available.",
    )
    parser.add_argument(
        "--label", type=str, default="",
        help="Tag the snapshot (e.g. 'before-phase2') so multiple baselines stay "
             "comparable in version control.",
    )
    parser.add_argument(
        "--out", type=str, default="benchmarks/results.json",
        help="Where to write the JSON report. Use '-' for stdout only.",
    )
    parser.add_argument(
        "--verbose", "-v", action="count", default=0,
        help="Increase logging verbosity (repeatable).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=max(logging.WARNING - 10 * args.verbose, logging.DEBUG),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    np.random.seed(args.seed)
    scenarios = list(SCENARIOS) if args.scenario == "all" else [args.scenario]

    results: list[dict] = []
    for name in scenarios:
        log.info("running scenario: %s", name)
        try:
            results.append(_run_scenario(
                name,
                trials=args.trials,
                iterations=args.iterations,
                with_camera=args.with_camera,
            ))
        except Exception as exc:  # noqa: BLE001
            log.exception("scenario %s failed: %s", name, exc)
            results.append({
                "scenario": name,
                "status": "error",
                "trials": 0,
                "iterations_per_trial": args.iterations,
                "reason": repr(exc),
            })

    report = {
        "python": sys.version.split()[0],
        "platform": platform.platform(terse=True),
        "git_describe": _git_describe(),
        "label": args.label,
        "seed": args.seed,
        "iterations_per_trial": args.iterations,
        "trials": args.trials,
        # CPU% is computed from `time.process_time`, which is the SUM of
        # all threads' CPU time in this process. For multi-threaded
        # scenarios (`server-fanout` runs ~4 worker threads) the metric
        # can therefore exceed 100% — think "process-wide CPU count",
        # not "this benchmark thread". Diff against this baseline on
        # apples-to-apples (same machine, same load).
        "cpu_pct_note": (
            "process_time is process-wide; scenarios that spawn worker "
            "threads (e.g. server-fanout with 1 accept + N handlers) "
            "include their CPU in `cpu_pct_mean`, so the metric may "
            "legitimately exceed 100%."
        ),
        "scenario_results": results,
    }
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.out != "-":
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        log.info("wrote %s", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
