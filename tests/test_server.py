"""End-to-end tests for `Server`.

Each test starts a real Server on an ephemeral TCP port (``port=0``,
``bind_retry=False``) in a background thread, drives it with two raw socket
clients, and calls :meth:`Server.shutdown` on teardown to drain workers.

Protocol note: the server only learns a peer's ``(i, s)`` once the peer has
sent at least one NDJSON frame. Tests therefore pre-register peers before
exchanging payloads — see :func:`_register`.
"""

from __future__ import annotations

import json
import socket
import threading
import time

import pytest

from server.main import Server
from s2c.framing import encode_line, Framer


def _wait_until(predicate, *, timeout: float = 2.0, interval: float = 0.01):
    """Spin-poll a predicate until it is truthy or timeout expires.

    Asserts on expiry so a hung server surfaces as a clear failure rather
    than letting downstream code run on broken state.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    assert predicate(), f"_wait_until timed out after {timeout}s"


def _drain_peek(sock: socket.socket, *, timeout: float = 0.5) -> list:
    """Read everything available within ``timeout`` and parse NDJSON frames."""
    sock.settimeout(timeout)
    out: list = []
    buf = b""
    try:
        while True:
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if line:
                    out.append(json.loads(line.decode()))
    finally:
        sock.settimeout(None)
    return out


@pytest.fixture
def server():
    srv = Server(port=0, bind_retry=False)
    t = threading.Thread(
        target=srv.serve_forever, daemon=True, name="test-server-accept",
    )
    t.start()
    yield srv
    srv.shutdown(timeout=2.0)


def _make_client(server) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", server.port))
    return s


def _register(
    server: Server,
    sock: socket.socket,
    sid: str,
    cid: str,
    *,
    hello_payload: str = "_init_",
):
    """Send a registration frame and wait for the server to record the peer."""
    sock.sendall(encode_line({"i": cid, "s": sid, "v": hello_payload}))
    _wait_until(
        lambda: cid in server.rooms.get(sid, {}),
        timeout=1.5,
    )


def _send(sock: socket.socket, sid: str, cid: str, payload: str) -> None:
    sock.sendall(encode_line({"i": cid, "s": sid, "v": payload}))


def _recv_next(sock: socket.socket, *, timeout: float = 2.0) -> dict:
    """Wait for the next NDJSON frame on `sock`. Raises on socket.timeout."""
    sock.settimeout(timeout)
    buf = b""
    try:
        while b"\n" not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                raise AssertionError(
                    f"peer closed before delivering a frame; buffered={buf!r}"
                )
            buf += chunk
    finally:
        sock.settimeout(None)
    line, _, rest = buf.partition(b"\n")
    if rest:
        # We don't accumulate ('framing' handles that). For tests we just
        # ensure the line ends correctly and discard any peek junk.
        pass
    return json.loads(line.decode())


# ----------------------------------------------------------------------------
# Bind / capacity / shutdown
# ----------------------------------------------------------------------------


def test_server_binds_ephemeral_port(server: Server) -> None:
    assert server.port > 0  # kernel assigned a real port
    assert server.rooms == {}


def test_two_clients_register_then_exchange(server: Server) -> None:
    sid = "lobby"
    a = _make_client(server)
    b = _make_client(server)
    _register(server, a, sid, "alice")
    _register(server, b, sid, "bob")
    # Drain any incidental hello-broadcast traffic on both sockets.
    _drain_peek(a, timeout=0.4)
    _drain_peek(b, timeout=0.4)
    _send(a, sid, "alice", "hi")
    received = _recv_next(b)
    assert received == {"i": "alice", "s": sid, "v": "hi"}
    _send(b, sid, "bob", "yo")
    received = _recv_next(a)
    assert received == {"i": "bob", "s": sid, "v": "yo"}


def test_partial_frame_then_completion(server: Server) -> None:
    sid = "lobby"
    a = _make_client(server)
    b = _make_client(server)
    _register(server, a, sid, "alice")
    _register(server, b, sid, "bob")
    _drain_peek(a, timeout=0.4)
    _drain_peek(b, timeout=0.4)

    full = encode_line({"i": "alice", "s": sid, "v": "PAR"})
    cut = len(full) // 2
    a.sendall(full[:cut])
    a.sendall(full[cut:])
    assert _recv_next(b) == {"i": "alice", "s": sid, "v": "PAR"}


def test_malformed_frame_dropped_then_resumed(server: Server) -> None:
    sid = "lobby"
    a = _make_client(server)
    b = _make_client(server)
    _register(server, a, sid, "alice")
    _register(server, b, sid, "bob")
    _drain_peek(a, timeout=0.4)
    _drain_peek(b, timeout=0.4)

    a.sendall(b"NOPE\n" + encode_line({"i": "alice", "s": sid, "v": "OK"}))
    assert _recv_next(b) == {"i": "alice", "s": sid, "v": "OK"}


# ----------------------------------------------------------------------------
# Cleanup / capacity / protocol errors
# ----------------------------------------------------------------------------


def test_dead_peer_removed_from_room(server: Server) -> None:
    sid = "lobby"
    a = _make_client(server)
    b = _make_client(server)
    _register(server, b, sid, "bob")  # ensure room has two peers
    _register(server, a, sid, "alice")
    assert "alice" in server.rooms[sid]
    a.close()
    _wait_until(
        lambda: "alice" not in server.rooms.get(sid, {}),
        timeout=2.0,
    )
    assert "alice" not in server.rooms.get(sid, {})


def test_room_capacity_capped_at_five(server: Server) -> None:
    sid = "cap-room"
    sockets = []
    for i in range(5):
        s = _make_client(server)
        _register(server, s, sid, f"p{i}")
        sockets.append(s)
    # 6th peer's payload must be dropped (not added to room).
    sixth = _make_client(server)
    sixth.sendall(encode_line({"i": "p6", "s": sid, "v": "x"}))
    # Trigger room-full via broadcast path — wait a slice to let server log.
    _wait_until(
        lambda: len(server.rooms.get(sid, {})) == 5,
        timeout=1.0,
    )
    assert len(server.rooms.get(sid, {})) == 5
    assert "p6" not in server.rooms.get(sid, {})
    for s in sockets:
        s.close()
    sixth.close()


def test_oversized_partial_frame_closes_connection(server: Server) -> None:
    """A partial frame > max_message_size must close the offending conn.

    Server treats the protocol violation as fatal: the handler breaks out
    and closes the socket, the client sees a FIN (empty recv).
    """
    sid = "lobby"
    a = _make_client(server)
    _register(server, a, sid, "alice")
    # Send 2 MiB of garbage with no newline — exceeds default 1 MiB before
    # completion, raising MessageSizeExceededError in the framer.
    a.sendall(b"X" * (1 << 21))
    # After the framer rejects the overgrown partial line, the server
    # half-closes (shutdown(SHUT_WR) + close()); the peer observes a
    # clean FIN (recv returns b"").
    a.settimeout(2.0)
    saw_fin = False
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not saw_fin:
        try:
            got = a.recv(64)
        except socket.timeout:
            continue
        if got == b"":
            saw_fin = True
    a.settimeout(None)
    assert saw_fin, "server did not FIN-close conn after oversized frame"
    a.close()


def test_shutdown_is_clean(server: Server) -> None:
    sid = "lobby"
    a = _make_client(server)
    _register(server, a, sid, "alice")
    server.shutdown(timeout=2.0)
    assert server.rooms == {}
    a.close()


# ----------------------------------------------------------------------------
# Defence: peer singled out as oversize NO newline must lose the conn.
# ----------------------------------------------------------------------------


def test_oversize_dropped_for_neighbours_not_replayed(server: Server) -> None:
    """A complete oversized line is dropped, neighbours see no junk."""
    sid = "lobby"
    a = _make_client(server)
    b = _make_client(server)
    _register(server, a, sid, "alice")
    _register(server, b, sid, "bob")
    _drain_peek(a, timeout=0.4)
    _drain_peek(b, timeout=0.4)

    line = (
        b'{"i":"alice","s":"lobby","v":"'
        + b"X" * (Framer.DEFAULT_MAX_MESSAGE_SIZE + 1024)
        + b'"}\n'
    )
    a.sendall(line)
    # Bob should NOT see a junk frame.
    junk = None
    b.settimeout(0.4)
    try:
        junk = b.recv(64)
    except socket.timeout:
        pass
    finally:
        b.settimeout(None)
    assert junk is None, f"neighbour received junk from dropped oversize: {junk!r}"
    # But subsequent, well-formed traffic still works.
    _send(a, sid, "alice", "ok-after-junk")
    assert _recv_next(b) == {"i": "alice", "s": sid, "v": "ok-after-junk"}
