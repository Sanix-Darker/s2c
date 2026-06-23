"""Phase 1 Client tests — no webcam, no microphone, no real socket.

These tests construct a :class:`Client` directly with a synthetic session and
drive individual methods with mocks. The hardware paths (``run``,
``_setup_media``, ``_send_frames`` main loop) are exercised in CI via the
``@pytest.mark.hardware`` group, which is skipped by default.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import time
from unittest.mock import MagicMock

import numpy as np
import pytest

from client.main import (
    CHARACTERS,
    Client,
    GLOBAL_BRIGHTNESSES,
    INDICES,
)
import client.main as client_main_module


HAS_CV2 = importlib.util.find_spec("cv2") is not None


@pytest.fixture
def fresh_start(monkeypatch: pytest.MonkeyPatch):
    """Reset the module-global START timer so tests are ordering-independent.

    ``get_fps`` derives its answer from the module-global ``START`` plus the
    call time. The original tests mutated ``START`` directly and polluted
    later tests. This fixture scopes the mutation to a single test.
    """
    monkeypatch.setattr(client_main_module, "START", time.time())


# ----------------------------------------------------------------------------
# __init__ / configuration
# ----------------------------------------------------------------------------


def _make_session() -> dict:
    return {
        "session_id": "test-session",
        "session_key": "test-key",
        "client_id": "test-client",
        "ip": "127.0.0.1",
        "port": 1234,
    }


def test_init_does_not_open_sockets_or_media() -> None:
    client = Client(_make_session())
    assert client.sock is None
    assert client.cam is None
    assert client.play_stream is None
    assert client.rec_stream is None
    assert client.faces == {}
    assert client.is_muted is False
    assert client.camera_enabled is True


def test_init_exposes_toggle_state() -> None:
    client = Client(_make_session())
    client.is_muted = True
    client.camera_enabled = False
    assert client.is_muted is True
    assert client.camera_enabled is False


def test_init_preserves_session_keys() -> None:
    s = _make_session()
    client = Client(s)
    assert client.session_id == s["session_id"]
    assert client.client_id == s["client_id"]
    assert client.session_key == s["session_key"]


def test_stop_sets_event() -> None:
    client = Client(_make_session())
    assert not client._stop.is_set()
    client.stop()
    assert client._stop.is_set()


# ----------------------------------------------------------------------------
# ASCII conversion helpers
# ----------------------------------------------------------------------------


def test_generate_frame_includes_fps_marker() -> None:
    """Smoke test: generate_frame always embeds fps_str into the output.

    The exact splice math (last ``len(fps_str)+1`` chars replaced by
    fps_str) is exercised by the underlying loop; Phase 2 will rewrite
    generate_frame for performance. Here we only assert the marker is
    present so this test survives future refactors.
    """
    gray = np.full((3, 5), 200, dtype=np.uint8)
    out = Client(_make_session()).generate_frame(
        "  9 FPS", gray, CHARACTERS, INDICES,
    )
    assert isinstance(out, str)
    assert "  9 FPS" in out
    # Has multiple newline-separated rows (since the build loop iterates per-row).
    assert "\n" in out


def test_generate_frame_preserves_string_type() -> None:
    """Smoke test: any (rows x cols) produces a string of reasonable length."""
    gray = np.zeros((2, 4), dtype=np.uint8)
    out = Client(_make_session()).generate_frame(
        " 30 FPS", gray, CHARACTERS, INDICES,
    )
    assert isinstance(out, str)
    assert len(out) > 0


def test_get_fps_returns_zero_for_zero_elapsed(fresh_start) -> None:
    """START == now → elapsed \u2248 0 \u2192 FPS floors to 0. Deterministic.

    Picking exactly t=0 sidesteps the math-vs-clock-skew flake in earlier
    drafts of this test.
    """
    client_main_module.START = time.time()
    s = Client(_make_session()).get_fps(0)
    assert s.strip().endswith("FPS")
    fps = int(s.strip().split()[0])
    assert fps == 0


@pytest.mark.skipif(not HAS_CV2, reason="cv2 not installed on this runner")
def test_ascii_it_with_black_white_image() -> None:
    client = Client(_make_session())
    # Pure white (BGR) → inverted grayscale → all 0 → top of CHARACTERS
    white = np.full((3, 3, 3), 255, dtype=np.uint8)
    # Pure black → inverted → nearly 255 → bottom of CHARACTERS
    black = np.zeros((3, 3, 3), dtype=np.uint8)
    out_black = client.ascii_it(black)
    out_white = client.ascii_it(white)
    assert isinstance(out_black, str)
    assert isinstance(out_white, str)
    assert "FPS" in out_black and "FPS" in out_white
    # Black image produces more of the "lightest" character (last in ramp)
    # than white image does.
    assert out_black.count(CHARACTERS[-1]) >= out_white.count(CHARACTERS[-1])


# ----------------------------------------------------------------------------
# Network send / receive
# ----------------------------------------------------------------------------


def test_send_now_serializes_to_ndjson() -> None:
    client = Client(_make_session())
    client.sock = MagicMock()
    client._send_now({"i": "me", "s": "r", "v": "ascii"})
    sent = client.sock.sendall.call_args[0][0]
    assert sent.endswith(b"\n")
    assert json.loads(sent.rstrip(b"\n")) == {"i": "me", "s": "r", "v": "ascii"}


def test_send_now_safe_when_socket_unset() -> None:
    client = Client(_make_session())
    client.sock = None
    # Must NOT raise
    client._send_now({"i": "me"})


def test_send_now_signals_stop_on_broken_socket() -> None:
    client = Client(_make_session())
    mock_sock = MagicMock()
    mock_sock.sendall.side_effect = OSError("nope")
    client.sock = mock_sock
    with pytest.raises(OSError):
        client._send_now({"i": "me", "s": "r", "a": "x"})
    # Stop indicator must be set so the surrounding loops exit cleanly.
    assert client._stop.is_set()


def test_recv_data_parses_ndjson_frames() -> None:
    client = Client(_make_session())
    mock_sock = MagicMock()
    payload_video = (
        b'{"i":"alice","s":"r","v":"ascii_frame"}\n'
        b'{"i":"alice","s":"r","v":"ascii_frame_2"}\n'
    )
    # First call returns the data, second raises OSError to break the loop.
    mock_sock.recv.side_effect = [payload_video, OSError("recv done")]
    client.sock = mock_sock
    client._recv_data()
    assert client.faces["alice"] == "ascii_frame_2"


def test_recv_data_dispatches_audio_to_speaker() -> None:
    client = Client(_make_session())
    pcm = b"\x00\x01\x02\x03" * 32
    enc = base64.b64encode(pcm).decode()
    payload = (
        f'{{"i":"alice","s":"r","a":"{enc}"}}\n'.encode()
    )
    mock_sock = MagicMock()
    mock_sock.recv.side_effect = [payload, OSError("recv done")]
    mock_speaker = MagicMock()
    client.sock = mock_sock
    client.play_stream = mock_speaker
    client._recv_data()
    mock_speaker.write.assert_called_once_with(pcm)


def test_recv_data_handles_empty_chunk_as_peer_close() -> None:
    client = Client(_make_session())
    client.sock = MagicMock()
    client.sock.recv.side_effect = [b"", OSError("not reached")]
    client._recv_data()
    assert client.faces == {}


def test_recv_data_malformed_audio_is_skipped_not_fatal() -> None:
    client = Client(_make_session())
    payload = (
        b'{"i":"alice","s":"r","a":"@@@not-base64@@@"}\n'
        b'{"i":"alice","s":"r","v":"x"}\n'
    )
    mock_sock = MagicMock()
    mock_sock.recv.side_effect = [payload, OSError("recv done")]
    mock_speaker = MagicMock()
    client.sock = mock_sock
    client.play_stream = mock_speaker
    client._recv_data()
    assert client.faces["alice"] == "x"
    mock_speaker.write.assert_not_called()


def test_recv_data_oversized_partial_frame_breaks_loop() -> None:
    """A partial frame > max_message_size triggers MessageSizeExceededError.

    The recv loop catches that and breaks, treating the peer as misbehaving.
    """
    client = Client(_make_session())
    client.sock = MagicMock()
    # Pure garbage with no newline — exceeds default 1 MiB after one feed.
    client.sock.recv.side_effect = [b"X" * (1 << 21), OSError("not reached")]
    client._recv_data()
    # No frames were parsed.
    assert client.faces == {}


# ----------------------------------------------------------------------------
# Audio send loop
# ----------------------------------------------------------------------------


def test_send_audio_emits_ndjson_with_base64_payload() -> None:
    client = Client(_make_session())
    pcm = b"\x10\x20\x30\x40" * 16
    mock_sock = MagicMock()
    mock_mic = MagicMock()
    mock_mic.read.side_effect = [pcm, OSError("mic done")]
    client.sock = mock_sock
    client.rec_stream = mock_mic
    client._send_audio()
    assert mock_sock.sendall.called
    sent = mock_sock.sendall.call_args[0][0]
    assert sent.endswith(b"\n")
    body = json.loads(sent.rstrip(b"\n"))
    assert body["i"] == "test-client"
    assert body["s"] == "test-session"
    assert base64.b64decode(body["a"]) == pcm


def test_send_audio_respects_mute_toggle() -> None:
    client = Client(_make_session())
    client.is_muted = True
    mock_sock = MagicMock()
    mock_mic = MagicMock()
    mock_mic.read.side_effect = [b"\x00" * 64, OSError("mic done")]
    client.sock = mock_sock
    client.rec_stream = mock_mic
    client._send_audio()
    mock_sock.sendall.assert_not_called()


# ----------------------------------------------------------------------------
# Render loop stays quiet when not invoked directly
# ----------------------------------------------------------------------------


def test_render_faces_calls_os_clear_and_print(monkeypatch: pytest.MonkeyPatch) -> None:
    client = Client(_make_session())
    called = {"count": 0}
    import builtins

    monkeypatch.setattr("os.system", lambda *a, **kw: None)

    def fake_print(*args, **kwargs):
        called["count"] += 1
        if called["count"] > 5:
            client.stop()

    monkeypatch.setattr(builtins, "print", fake_print)
    # 60x20 size ensures _render_faces iterates SIZE[1] = 20 rows.
    client.faces = {
        "alice": "\n".join("x" * 60 for _ in range(client.SIZE[1])),
    }
    client._render_faces()
    assert called["count"] > 0
