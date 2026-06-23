"""NDJSON framing helpers shared by client and server.

A Framer accumulates bytes from a stream and yields one complete JSON dict
per '\\n' boundary. It is deliberately small and stateful so it can be reused
from a blocking `socket.recv` loop *and* an asyncio `StreamReader.feed_data`
loop without changes.

Recovery rules:
- Malformed JSON (after the accumulator contains a '\\n') is logged and skipped
  so a single bad line cannot wedge the whole stream.
- A message larger than `max_message_size` triggers `MessageSizeExceededError`.
  The buffer is reset so the stream continues to make progress.
"""

from __future__ import annotations

import json
import logging
from typing import Iterator


log = logging.getLogger("s2c.framing")


class MessageSizeExceededError(Exception):
    """Raised by Framer.feed when an incoming line exceeds max_message_size.

    The Framer resets its internal buffer on this path so the next call to
    `feed` begins cleanly at offset 0. Callers should treat this as a fatal
    protocol violation against the peer that sent the offending payload.
    """


class Framer:
    """Stateful NDJSON byte accumulator.

    Wire format: one JSON object per line, terminated by '\\n'. Lines may be
    split across many `feed()` calls; multiple lines can arrive in a single
    `feed()` call.

    Usage::

        framer = Framer()
        for chunk in socket_recv_loop():
            for pkt in framer.feed(chunk):
                handle(pkt)

    Args:
        max_message_size: Hard cap on any single frame's byte length. Default
            1 MiB which is far above any well-behaved audio chunk yet small
            enough to detect malicious peers quickly.
    """

    DEFAULT_MAX_MESSAGE_SIZE = 1 << 20  # 1 MiB

    __slots__ = ("_buf", "_max")

    def __init__(self, max_message_size: int = DEFAULT_MAX_MESSAGE_SIZE) -> None:
        if max_message_size <= 0:
            raise ValueError("max_message_size must be positive")
        self._buf = bytearray()
        self._max = max_message_size

    @property
    def buffered_bytes(self) -> int:
        """Number of bytes currently held in the accumulator (mostly for tests)."""
        return len(self._buf)

    def reset(self) -> None:
        """Discard everything accumulated. Useful after a fatal protocol error."""
        self._buf.clear()

    def feed(self, data: bytes) -> Iterator[dict]:
        """Consume `data` and yield each complete JSON object found.

        Splits on '\\n'. A trailing partial frame is retained for the next call.
        Empty lines are skipped.
        """
        if not data:
            return
        self._buf.extend(data)
        # Fast path: nothing to do if no newline present
        if b"\n" not in self._buf:
            self._guard_overflow()
            return
        # Split on the first newline boundary, then continue for remaining lines
        while True:
            newline_idx = self._buf.find(b"\n")
            if newline_idx == -1:
                break
            line = bytes(self._buf[:newline_idx])
            del self._buf[: newline_idx + 1]
            if not line:
                continue
            if len(line) > self._max:
                # Discard the offending line, keep the rest of the stream alive.
                log.warning(
                    "framer: dropping oversized frame (%d > %d bytes)",
                    len(line),
                    self._max,
                )
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                log.warning("framer: skipping malformed JSON: %s", exc)
                continue
            if not isinstance(obj, dict):
                log.debug("framer: non-dict frame skipped (got %s)", type(obj).__name__)
                continue
            yield obj
        self._guard_overflow()

    def _guard_overflow(self) -> None:
        if len(self._buf) > self._max:
            self._buf.clear()
            raise MessageSizeExceededError(
                f"incomplete frame already exceeds max_message_size={self._max}; "
                "buffer reset so the stream can recover."
            )


def encode(obj: dict) -> bytes:
    """Serialize `obj` as a single NDJSON line (no trailing newline).

    Centralized so the wire format stays identical on both sides.
    """
    return json.dumps(obj, separators=(",", ":")).encode()


def encode_line(obj: dict) -> bytes:
    """Serialize `obj` as a complete '\n'-terminated NDJSON line."""
    return encode(obj) + b"\n"
