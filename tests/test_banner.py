"""Banner / startup-print regression tests.

`_start_threads` writes to stdout directly (no logging). Capture via
`contextlib.redirect_stdout` so the regression test runs without
contaminating test output. Covers US-C04 ("banner prints on connect") and
US-C13 ("startup prints session info").
"""

from __future__ import annotations

import contextlib
import io

import pytest

from client.main import Client


@pytest.fixture
def client_minimal() -> Client:
    """A Client built from an in-memory session dict; not connected.

    The fixture sets ``_stop`` on teardown so the daemon threads spawned by
    `_start_threads` exit cleanly before the test framework moves on. That
    avoids the threads printing to test stdout after ``redirect_stdout``
    has already restored the real writer.
    """
    client = Client({
        "session_key": "s2c_DEAD",
        "session_id": "fixed-session-id-1234",
        "client_id": "fixed-client-id-5678",
        "ip": "127.0.0.1",
        "port": 0,
    })
    yield client
    client._stop.set()


def test_banner_contains_session_metadata(client_minimal: Client) -> None:
    """US-C04 banner lines must include session_id, client_id, session_key."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        client_minimal._start_threads()
    text = buf.getvalue()
    # The banner prints 5 lines:
    #   "[-] s2c started..."
    #   "[>] session_id : ..."
    #   "[<] client_id : ..."
    #   "[:] session_key : ..."
    #   "[-] Connected to Server\n"
    assert "[-] s2c started" in text, (
        f"Banner missing the `[-] s2c started` line; got: {text!r}"
    )
    assert "[>] session_id : fixed-session-id-1234" in text, (
        f"Banner missing session_id line; got: {text!r}"
    )
    assert "[<] client_id : fixed-client-id-5678" in text, (
        f"Banner missing client_id line; got: {text!r}"
    )
    assert "[:] session_key : s2c_DEAD" in text, (
        f"Banner missing session_key line; got: {text!r}"
    )
    assert "Connected to Server" in text, (
        f"Banner missing the `[-] Connected to Server` line; got: {text!r}"
    )


def test_banner_mentions_connected_status(client_minimal: Client) -> None:
    """US-C04 follow-on: banner ends with the "Connected to Server" line."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        client_minimal._start_threads()
    text = buf.getvalue()
    assert "Connected to Server" in text, (
        f"Banner must end with '[-] Connected to Server'; got: {text!r}"
    )


def test_banner_does_not_crash_when_session_metadata_is_short(
    client_minimal: Client,
) -> None:
    """Regression: short session ids shouldn't trip the format string."""
    client_minimal.client_id = "abc"
    client_minimal.session_id = "x"
    client_minimal.session_key = "k"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        # Must not raise.
        client_minimal._start_threads()
    assert "[<] client_id : abc" in buf.getvalue()
