"""Adversarial NDJSON Framer tests.

Covers partial frames, multiple frames per recv, malformed JSON, oversized
payloads and the encoder helpers shared between client and server.
"""

from __future__ import annotations

import json

import pytest

from s2c.framing import (
    Framer,
    MessageSizeExceededError,
    encode,
    encode_line,
)


def _drain(framer: Framer, data: bytes) -> list:
    return list(framer.feed(data))


def test_empty_feed_yields_nothing() -> None:
    f = Framer()
    assert _drain(f, b"") == []


def test_single_complete_message() -> None:
    f = Framer()
    assert _drain(f, b'{"i":"alice","s":"r","v":"hi"}\n') == [
        {"i": "alice", "s": "r", "v": "hi"}
    ]
    assert f.buffered_bytes == 0


def test_two_messages_in_one_feed() -> None:
    f = Framer()
    payload = b'{"a":1}\n{"b":2}\n'
    assert _drain(f, payload) == [{"a": 1}, {"b": 2}]
    assert f.buffered_bytes == 0


def test_partial_then_completion_across_feeds() -> None:
    f = Framer()
    full = b'{"i":"bob","s":"r","v":"OH"}\n'
    half = len(full) // 2
    assert _drain(f, full[:half]) == []
    assert f.buffered_bytes == half
    assert _drain(f, full[half:]) == [{"i": "bob", "s": "r", "v": "OH"}]


def test_multiple_frames_split_in_second_feed() -> None:
    f = Framer()
    # First feed carries two frames complete + half of a third
    part1 = b'{"a":1}\n{"a":2}\n{"a":'
    out = _drain(f, part1)
    assert out == [{"a": 1}, {"a": 2}]
    assert f.buffered_bytes == len(part1) - (len(b'{"a":1}\n') + len(b'{"a":2}\n'))
    # Second feed completes the third + adds a fourth
    part2 = b'3}\n{"a":4}\n'
    out = _drain(f, part2)
    assert out == [{"a": 3}, {"a": 4}]


def test_malformed_json_skipped() -> None:
    f = Framer()
    data = b'{"a":1}\nNOPE\n{"a":2}\n'
    assert _drain(f, data) == [{"a": 1}, {"a": 2}]


def test_non_dict_frames_skipped() -> None:
    f = Framer()
    assert _drain(f, b'[1,2,3]\n{"ok":1}\n') == [{"ok": 1}]


def test_empty_lines_skipped() -> None:
    f = Framer()
    data = b'\n\n{"a":1}\n\n\n{"a":2}\n'
    assert _drain(f, data) == [{"a": 1}, {"a": 2}]


def test_oversized_line_is_dropped_not_buffered() -> None:
    f = Framer(max_message_size=64)
    huge_payload = b'{"x":"' + b"A" * 1000 + b'"}\n'
    # Framer drops the offending line and continues for subsequent messages.
    assert _drain(f, huge_payload) == []
    # A subsequent small frame still works.
    assert _drain(f, b'{"a":1}\n') == [{"a": 1}]


def test_incomplete_frame_overflow_raises() -> None:
    f = Framer(max_message_size=8)
    # 9 bytes without a newline → raises immediately on _guard_overflow()
    with pytest.raises(MessageSizeExceededError):
        _drain(f, b'{"a":1234')
    # After the guard, the buffer is reset.
    assert f.buffered_bytes == 0


def test_reset_clears_buffer() -> None:
    f = Framer()
    _drain(f, b'{"a":1,')
    assert f.buffered_bytes > 0
    f.reset()
    assert f.buffered_bytes == 0


def test_max_message_size_must_be_positive() -> None:
    with pytest.raises(ValueError):
        Framer(max_message_size=0)


def test_encode_produces_no_trailing_newline() -> None:
    assert encode({"a": 1}) == b'{"a":1}'


def test_encode_line_appends_newline() -> None:
    line = encode_line({"a": 1})
    assert line.endswith(b"\n")
    assert json.loads(line.rstrip(b"\n")) == {"a": 1}


def test_realistic_video_frame_round_trip() -> None:
    # Simulated 60x20 ASCII frame payload produced by an upstream peer.
    fake_ascii = "\n".join("A" * 60 for _ in range(20)) + "\n  15 FPS"
    pkt = {"i": "peer-1", "s": "lobby", "v": fake_ascii}
    f = Framer()
    framer_output = _drain(f, encode_line(pkt))
    assert framer_output == [pkt]
