"""Client for s2c.

Phase 1 implementation:
- ``Client.__init__`` is **configuration only** — it sets attributes but
  performs no socket, camera, or microphone I/O. Tests construct a ``Client``
  with no hardware access required.
- ``Client.run()`` is the production entry point: it opens the socket, the
  camera and the audio device, spawns the three worker threads and blocks on
  the main frame send loop.
- ``cv2`` and ``pyaudio`` imports are deferred to the methods that actually
  use them so a test that never calls ``run()`` or ``ascii_it`` does not need
  the C bindings to be installed.
- Inbound network data flows through :class:`s2c.framing.Framer`; the
  accumulator tolerates partial and coalesced TCP segments.
- Numpy-backed ASCII conversion is unchanged in Phase 1; Phase 2 will
  vectorize ``generate_frame`` and ``ascii_it`` to remove the Python-level
  per-pixel loop.
"""

from __future__ import annotations

import argparse
import base64
import logging
import os
import socket
import threading
import time
from bisect import bisect
from typing import Optional

import numpy as np

from s2c.cli_args import build_parser, parse_session
from s2c.framing import Framer, MessageSizeExceededError, encode_line


log = logging.getLogger("s2c.client")


# fmt: off
CHARACTERS = [
    "M", "B", "N", "W", "R", "g", "#", "Q", "8", "D", "$", "0", "H", "@", "m",
    "&", "E", "O", "9", "6", "d", "b", "A", "p", "K", "q", "Z", "G", "U", "X",
    "P", "5", "a", "2", "S", "k", "e", "h", "4", "V", "3", "I", "w", "F", "y",
    "o", "{", "}", "f", "C", "u", "n", "1", "z", "%", "s", "t", "x", "Y", "J",
    "[", "T", "]", "j", "7", "L", "i", "l", "v", "c", "?", ")", "(", "/", "r",
    "<", ">", "*", "=", "|", "+", "!", "_", ";", "^", ":", "~", ",", ".", "-",
    "`", " ",
]
GLOBAL_BRIGHTNESSES = np.array([
    156.1, 157.6, 159.9, 160.6, 164.8, 165.6, 166.3, 167.1, 168.9, 169.9,
    171.2, 171.6, 172.1, 172.2, 172.4, 173.5, 173.7, 173.9, 173.9, 174.0,
    174.7, 174.7, 174.9, 176.3, 176.3, 176.4, 176.7, 177.4, 179.2, 179.5,
    179.6, 180.0, 181.2, 181.4, 182.1, 182.2, 182.3, 184.6, 184.9, 185.7,
    186.7, 188.1, 189.1, 189.7, 192.0, 192.3, 194.5, 194.5, 195.1, 195.7,
    195.7, 195.8, 196.0, 196.3, 196.7, 196.8, 197.9, 198.6, 198.7, 198.9,
    199.2, 199.2, 199.2, 200.0, 200.5, 202.4, 202.4, 203.3, 203.9, 205.9,
    208.9, 214.7, 214.8, 215.2, 215.5, 215.8, 215.8, 220.8, 223.1, 223.1,
    225.2, 225.6, 229.5, 230.5, 231.7, 238.0, 238.7, 239.0, 246.5, 246.5,
    248.3, 255.0,
])
# fmt: on

INDICES: list[int] = [0] * 256

FRAMES = 0
START = time.time()


class Client:
    """Phase 1 client: connect, send/receive, render.

    Constructor only stores configuration — no I/O. Tests can fabricate a
    Client from a fake session dict and override ``run`` by calling the
    individual ``_send_*`` / ``_recv_data`` methods with mocks.
    """

    CHUNK = 512
    RATE = 10_000
    SIZE = (60, 20)

    # ---- configuration -----------------------------------------------------

    def __init__(self, session: dict) -> None:
        self.session = session
        self.session_key = session["session_key"]
        self.session_id = session["session_id"]
        self.client_id = session["client_id"]

        self.faces: dict[str, str] = {}
        self.lock = threading.Lock()

        self.sock: Optional[socket.socket] = None
        self.cam = None
        self.play_stream = None
        self.rec_stream = None

        # Toggles for hotkeys (Phase 3 wires them via textual actions).
        self.is_muted = False
        self.camera_enabled = True
        self.target_fps = 15
        self._stop = threading.Event()

    # ---- production entry point -------------------------------------------

    def run(self) -> None:
        """Production entry: open everything and block on the frame loop."""
        self._connect()
        self._setup_media()
        self._start_threads()
        try:
            self._send_frames()
        except KeyboardInterrupt:
            log.info("KeyboardInterrupt received; exiting run()")
            self.stop()

    def stop(self) -> None:
        """Cooperative shutdown — safe from any thread."""
        self._stop.set()

    def quit(self) -> None:
        """Hard shutdown used by Signal handlers and atexit hooks."""
        self._stop.set()

    # ---- lifecycle ----------------------------------------------------------

    def _connect(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        attempt = 0
        while not self._stop.is_set():
            err = sock.connect_ex((self.session["ip"], self.session["port"]))
            if err == 0:
                self.sock = sock
                return
            attempt += 1
            if attempt % 30 == 0:
                log.warning(
                    "still trying to connect to %s:%s (attempt %d, last errno=%d)",
                    self.session["ip"],
                    self.session["port"],
                    attempt,
                    err,
                )
            time.sleep(1)
        sock.close()
        raise SystemExit("client: connect aborted by stop()")

    def _setup_media(self) -> None:
        """Open the local camera and mic. Imports are deferred so tests skip them."""
        from cv2 import VideoCapture  # type: ignore[import-not-found]
        try:
            import pyaudio  # type: ignore[import-not-found]
        except OSError as exc:  # pragma: no cover - hardware-dependent
            raise RuntimeError(
                "pyaudio could not open the default audio device. "
                "On Linux/macOS install portaudio (e.g. "
                "`sudo apt install -y portaudio19-dev`) before running the client."
            ) from exc

        self.cam = VideoCapture(0)
        self.cam.set(3, self.SIZE[0])
        self.cam.set(4, self.SIZE[1])

        pa = pyaudio.PyAudio()
        self.play_stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.RATE,
            output=True,
            frames_per_buffer=self.CHUNK,
        )
        self.rec_stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK,
        )

    def _start_threads(self) -> None:
        print("[-] s2c started...")
        print(f"[>] session_id : {self.session_id}")
        print(f"[<] client_id : {self.client_id}")
        print(f"[:] session_key : {self.session_key}")
        print("[-] Connected to Server\n")

        threading.Thread(
            target=self._recv_data, daemon=True, name="s2c-recv",
        ).start()
        threading.Thread(
            target=self._send_audio, daemon=True, name="s2c-audio",
        ).start()
        threading.Thread(
            target=self._render_faces, daemon=True, name="s2c-render",
        ).start()

    # ---- transport ----------------------------------------------------------

    def _send_now(self, payload: dict) -> None:
        """Encode `payload` as NDJSON and push it down the wire.

        Uses the shared :func:`s2c.framing.encode_line` so the wire format
        stays identical to what the server broadcasts back.
        """
        sock = self.sock
        if sock is None:
            return
        try:
            sock.sendall(encode_line(payload))
        except OSError as exc:
            log.warning("sendall failed: %s — requesting stop", exc)
            self.stop()
            raise

    def _recv_data(self) -> None:
        """Receive NDJSON frames; dispatch audio playback or video faces."""
        sock = self.sock
        if sock is None:
            return
        framer = Framer()
        while not self._stop.is_set():
            try:
                chunk = sock.recv(4096)
            except OSError as exc:
                log.debug("recv failed: %s", exc)
                break
            if not chunk:
                log.debug("recv returned empty — peer closed")
                break
            try:
                self._dispatch_chunk(framer, chunk)
            except MessageSizeExceededError as exc:
                log.warning(
                    "oversized frame from server; aborting recv loop: %s", exc,
                )
                break

    def _dispatch_chunk(self, framer: Framer, chunk: bytes) -> None:
        """Feed chunk to `framer` and dispatch every yielded frame.

        Kept in its own method so the try/except for :class:`MessageSizeExceededError`
        in ``_recv_data`` covers raises that happen inside the generator
        (mid-iteration), not only ones raised at the start of ``feed``.

        Honours :attr:`_stop` between yielded frames so a peer that
        extrapolated a giant TCP chunk can't keep us from quitting cleanly.
        """
        for msg in framer.feed(chunk):
            if self._stop.is_set():
                break
            cid = msg.get("i")
            if not cid:
                log.debug("frame without cid ignored: %r", msg)
                continue
            if "a" in msg:
                try:
                    data = base64.b64decode(msg["a"])
                except (TypeError, ValueError):
                    log.debug("malformed audio payload; ignored")
                    continue
                stream = self.play_stream
                if stream is not None:
                    try:
                        stream.write(data)
                    except OSError:
                        log.debug("play_stream.write failed; ignored")
            if "v" in msg:
                with self.lock:
                    self.faces[cid] = msg["v"]


    def _send_audio(self) -> None:
        """Mic → socket. Honours :attr:`is_muted` cooperatively."""
        while not self._stop.is_set():
            stream = self.rec_stream
            if stream is None:
                break
            try:
                chunk = stream.read(self.CHUNK, exception_on_overflow=False)
            except OSError as exc:
                log.debug("mic read failed: %s", exc)
                break
            if self.is_muted:
                continue
            self._send_now({
                "i": self.client_id,
                "s": self.session_id,
                "a": base64.b64encode(chunk).decode(),
            })

    def _send_frames(self) -> None:  # pragma: no cover - hardware loop
        """Camera → ASCII → socket. Blocks until Ctrl-C or :meth:`stop`."""
        from cv2 import resize, flip  # deferred
        try:
            while not self._stop.is_set():
                if not self.camera_enabled:
                    time.sleep(0.1)
                    continue
                cam = self.cam
                if cam is None:
                    time.sleep(0.1)
                    continue
                ok, frame = cam.read()
                if not ok:
                    continue
                ascii_frame = self.ascii_it(flip(resize(frame, self.SIZE), 1))
                with self.lock:
                    self.faces[self.client_id] = ascii_frame
                self._send_now({
                    "i": self.client_id,
                    "s": self.session_id,
                    "v": ascii_frame,
                })
        finally:
            cam = self.cam
            if cam is not None:
                try:
                    cam.release()
                except Exception:  # pragma: no cover
                    pass

    def _render_faces(self) -> None:
        """Phase-1 render loop. Phase 3 replaces this with a textual widget."""
        clear = "cls" if os.name == "nt" else "clear"
        while not self._stop.is_set():
            os.system(clear)
            print("-" * 30)
            print(f"[+] s2c | session_id : {self.session_id}")
            print("-" * 30)

            with self.lock:
                keys = list(self.faces)
                left, right = keys[:3], keys[3:]
                _lines = {
                    k: self.faces[k].split("\n")[: self.SIZE[1]] for k in keys
                }
                _uid = {k: f"client_id: {k}" for k in keys}
                _width = {
                    k: max(len(_uid[k]), *(len(li) for li in _lines[k]))
                    for k in keys
                }

            def block(cols):
                rows = []
                for i in range(self.SIZE[1]):
                    parts = []
                    for k in cols:
                        cell = (
                            _uid[k]
                            if i == 0
                            else (_lines[k][i] if i < len(_lines[k]) else "")
                        )
                        parts.append(cell.ljust(_width[k]))
                    if parts:
                        rows.append(" | ".join(parts))
                return "\n".join(rows)

            print(block(left))
            if right:
                print("\n" + "-" * 30)
                print(block(right))

            time.sleep(0.05)

    # ---- ASCII conversion ---------------------------------------------------

    def generate_frame(self, fps_str, gray_image, characters, indices):
        string = ""
        for row in gray_image:
            for c in row:
                string += characters[indices[c]]
            string += "\n"
        string = string[: -len(fps_str) - 1] + fps_str
        return string

    def get_fps(self, frames):
        fps = int(frames // (time.time() - START))
        return "  {} FPS".format(fps)

    def ascii_it(self, image):
        """BGR frame → multi-line ASCII art. Phase 2 will vectorize this."""
        from cv2 import cvtColor, COLOR_BGR2GRAY  # type: ignore[import-not-found]
        global FRAMES

        gray_image = 255 - cvtColor(image, COLOR_BGR2GRAY)

        upper_limit = gray_image.max() * (
            (len(CHARACTERS) + 1) / float(len(CHARACTERS))
        )
        lower_limit = gray_image.min()

        bright_div = (GLOBAL_BRIGHTNESSES - GLOBAL_BRIGHTNESSES.min()) / (
            GLOBAL_BRIGHTNESSES.max() - GLOBAL_BRIGHTNESSES.min()
        )
        brightnesses = (
            bright_div * (upper_limit - lower_limit) + lower_limit
        )

        FRAMES += 1
        fps_str = self.get_fps(FRAMES)

        for c in range(int(gray_image.min()), int(gray_image.max()) + 1):
            INDICES[c] = bisect(brightnesses, c)

        return self.generate_frame(fps_str, gray_image, CHARACTERS, INDICES)


# ---- legacy entry --------------------------------------------------------------

def main() -> int:
    """`python -m client.main` entry. Behaviour-compatible with the original script."""
    args = build_parser(prog="client").parse_args()
    client = Client(parse_session(args))
    client.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
