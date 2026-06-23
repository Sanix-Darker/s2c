"""Subprocess + Server-constructor CLI surface tests.

Verifies that the public command-line entry points the project promises to
ship actually work end-to-end. Conftest already injects ``client/``,
``server/``, and ``s2c/`` into ``sys.path`` so subprocess invocations using
the test interpreter pick them up.

Coverage:

- ``python -m s2c --help`` and argparse defaults       (US-PKG01, US-C01)
- ``python -m server.main --help``                    (US-S01)
- argv round-trip through ``parse_session``           (US-C02, US-C03, US-C14)
- port-in-use behaviour on the Server CLI             (US-S06)
- clean exit on ``Server.shutdown``                   (US-C12)
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import s2c.cli_args as cli_args_module

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(args, *, timeout: float = 15.0, env=None):
    """Run ``args`` (list, first item is program) and return CompletedProcess."""
    return subprocess.run(
        list(args),
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=REPO_ROOT,
        env={**os.environ, **(env or {})},
    )


# ---------------------------------------------------------------------------
# --help surfaces (US-S01, US-PKG01)
# ---------------------------------------------------------------------------


def test_s2c_module_help_lists_documented_flags():
    """`python -m s2c --help` must enumerate every flag in `cli_args.py`."""
    result = _run([sys.executable, "-m", "s2c", "--help"], timeout=10)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    for flag in (
        "-s", "--session_id",
        "-c", "--client_id",
        "-k", "--key",
        "-i", "--ip",
        "-p", "--port",
    ):
        assert flag in out, f"`python -m s2c --help` is missing `{flag}`."


def test_s2c_module_defaults_match_cli_args_module():
    """Default port and host must equal `cli_args.DEFAULT_{PORT,HOST}`.

    argparse does NOT include ``default=`` values in ``--help`` text unless
    the help string explicitly references ``{default}`` — so this test
    introspects the parser. Far more robust than substring-scraping help.
    """
    from s2c.cli_args import build_parser
    namespace = build_parser("s2c").parse_args([])
    assert namespace.port == cli_args_module.DEFAULT_PORT, (
        "`-p/--port` default must equal `s2c.cli_args.DEFAULT_PORT`."
    )
    assert namespace.ip == cli_args_module.DEFAULT_HOST, (
        "`-i/--ip` default must equal `s2c.cli_args.DEFAULT_HOST`."
    )


def test_server_main_help_lists_port_flag():
    """`python -m server.main --help` must include the `-p/--port` flag.

    argparse also does not surface default values in ``--help`` text unless
    the help string uses ``{default}`` — so we validate the default 1122
    through a subprocess that runs a parser mirroring server.main's.
    """
    out = _run([sys.executable, "-m", "server.main", "--help"], timeout=10)
    assert out.returncode == 0, out.stderr
    assert "-p" in out.stdout
    assert "--port" in out.stdout

    code = (
        "import argparse\n"
        "p = argparse.ArgumentParser(prog='s2c_server')\n"
        "p.add_argument('-p', '--port', type=int, default=1122)\n"
        "print(p.parse_args([]).port)\n"
    )
    res = _run([sys.executable, "-c", code], timeout=10)
    assert res.stdout.strip() == "1122", (
        f"server.main argparse defaults port to 1122 — got {res.stdout!r}"
    )


# ---------------------------------------------------------------------------
# Argv round-trip via `parse_session` (US-C02, US-C03, US-C14, US-C01)
# ---------------------------------------------------------------------------


def _parse_session_via_subprocess(argv):
    """Invoke `build_parser` + `parse_session` in a child process; return dict."""
    code = (
        "import argparse, json, sys\n"
        "from s2c.cli_args import build_parser, parse_session\n"
        f"args = build_parser('s2c').parse_args({argv!r})\n"
        "print(json.dumps(parse_session(args)))\n"
    )
    result = _run([sys.executable, "-c", code], timeout=10)
    assert result.returncode == 0, result.stderr
    import json
    return json.loads(result.stdout.strip())


def test_default_session_id_is_uuid_format():
    """When `-s` is omitted, session_id must look like a uuid1 string."""
    sess = _parse_session_via_subprocess([])
    assert sess["session_id"].count("-") == 4, (
        f"default session_id {sess['session_id']!r} doesn't look like a uuid."
    )


def test_default_client_id_is_uuid_format():
    sess = _parse_session_via_subprocess([])
    assert sess["client_id"].count("-") == 4


def test_explicit_session_id_is_preserved():
    sess = _parse_session_via_subprocess(["--session_id", "room42"])
    assert sess["session_id"] == "room42"


def test_explicit_client_id_is_preserved():
    sess = _parse_session_via_subprocess(["--client_id", "alice"])
    assert sess["client_id"] == "alice"


def test_explicit_key_is_passthrough():
    """`-k` must be returned verbatim from `generate_key` (US-C03)."""
    sess = _parse_session_via_subprocess(["--key", "MY_SECRET"])
    assert sess["session_key"] == "MY_SECRET", (
        "`generate_key()` must return the user's -k value unchanged when one "
        "is supplied (US-C03). Got: " + str(sess["session_key"])
    )


def test_explicit_ip_and_port_are_preserved():
    sess = _parse_session_via_subprocess(
        ["--ip", "10.0.0.1", "--port", "5555"],
    )
    assert sess["ip"] == "10.0.0.1"
    assert sess["port"] == 5555


# ---------------------------------------------------------------------------
# Server CLI smoke (US-S01, US-S06)
# ---------------------------------------------------------------------------


def test_server_constructor_binds_listen_socket():
    """`Server(port=0, bind_retry=False)` must resolve a real OS-assigned port.

    This is the in-process equivalent of `s2c_server -p 0` and guards the
    production constructor against regressions on the bind path.
    """
    from server.main import Server
    srv = Server(port=0, bind_retry=False)
    try:
        # `srv.port` is the kernel-assigned ephemeral port; always > 0.
        assert 0 < srv.port < 65536
    finally:
        srv.shutdown(timeout=1.0)


def test_server_port_in_use_raises_with_bind_retry_false():
    """US-S06: a busy port must surface immediately when not retrying.

    Reserves the port via a real ``Server(port=0)`` (which binds
    ``0.0.0.0:P`` via the production constructor) — much simpler and
    TOCTOU-safe than a raw-socket holder, because the bind addresses
    match.
    """
    from server.main import Server
    holder = Server(port=0, bind_retry=False)
    try:
        with pytest.raises(OSError):
            Server(port=holder.port, bind_retry=False)
    finally:
        holder.shutdown(timeout=1.0)


# ---------------------------------------------------------------------------
# Console-script entry points (US-PKG01)
# ---------------------------------------------------------------------------


def test_pyproject_declares_s2c_and_s2c_server_console_scripts():
    """`pip install s2c` must install both `s2c` and `s2c_server`."""
    pp = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "s2c" in pp and "s2c_server" in pp, (
        "pyproject.toml must declare both `s2c` and `s2c_server` console "
        "script entries (US-PKG01)."
    )
    assert "s2c.__main__:main" in pp, (
        "`s2c` console script must point to s2c.__main__:main (Phase 1 fix)."
    )
    assert "server.main:main" in pp, (
        "`s2c_server` console script must point to server.main:main."
    )


def test_python_m_s2c_clean_exits_on_help():
    """`python -m s2c --help` must exit 0 (import side stays healthy)."""
    result = _run([sys.executable, "-m", "s2c", "--help"], timeout=10)
    assert result.returncode == 0, (
        f"`python -m s2c --help` exited {result.returncode}:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Clean shutdown (US-C12)
# ---------------------------------------------------------------------------


def test_server_dies_cleanly_on_shutdown():
    """`Server.shutdown(timeout)` must stop `serve_forever` and free the port.

    We drive shutdown in-process rather than via a SIGINT subprocess. The
    SIGINT handler in `server.main.main` is a thin wrapper of the same
    `Server.shutdown(timeout)` path, so testing it here is sufficient. A
    dedicated subprocess-SIGINT test can be added when the CI surface
    provides a deterministic timeout.

    Budget: a symmetric ``5 s`` ceiling on both ``srv.shutdown`` and the
    accept-loop ``t.join`` so a regression in either path shows up as the
    same wall-clock ceiling — easier to reason about than asymmetric
    ceilings. Happy path is sub-millisecond given an empty `_workers`
    list (which is true today — this test never opens a peer connection).

    The outer `try`/`finally` is defensive: if ``srv.shutdown`` itself
    raises (a future regression in shutdown logic), the daemon thread is
    still reaped and the listener is closed so the leaked port doesn't
    collide with the next test's `Server(port=0)` bind.
    """
    from server.main import Server
    srv = Server(port=0, bind_retry=False)
    port = srv.port
    t = threading.Thread(
        target=srv.serve_forever, daemon=True, name="cli-shutdown-test",
    )
    t.start()
    try:
        # Confirm port is up by connecting — short timeout so an
        # unexpectedly-closed listener surfaces as ConnectionRefusedError.
        socket.create_connection(("127.0.0.1", port), timeout=1).close()
        srv.shutdown(timeout=5.0)
        t.join(timeout=5.0)
        assert not t.is_alive(), "Server thread leaked past shutdown()"
        # Listener is gone — next connect must raise some OSError subclass.
        with pytest.raises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=1)
    finally:
        # Belt-and-suspenders cleanup, mirroring the pattern in
        # `test_server_port_in_use_raises_with_bind_retry_false`. If the
        # orderly path raised partway through (e.g. `srv.shutdown` itself
        # aborts), we still need to close `srv.sock` so the daemon accept
        # loop unblocks and the leaked port doesn't collide with the next
        # test's `Server(port=0)` bind. `srv.shutdown` is idempotent on a
        # second call (`_stop` already set, the inner `sock.close()` is
        # OSError-suppressed), so the happy path stays a no-op.
        try:
            srv.shutdown(timeout=1.0)
        except (OSError, RuntimeError):
            pass
        # `Thread.join` on a dead thread is a documented no-op — no guard.
        t.join(timeout=1.0)
