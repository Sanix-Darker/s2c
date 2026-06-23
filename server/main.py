"""S2C chat server.

Phase 1 implementation:
- NDJSON framing via ``s2c.framing.Framer`` so partial or coalesced TCP
  segments no longer crash ``json.loads``.
- Idempotent dead-peer cleanup via :meth:`Server._remove_peer` and
  :meth:`Server._find_and_remove` (re-entrancy safe under the room lock).
- :meth:`Server.shutdown` so tests (and SIGINT handlers) can stop accepting
  and drain all writers deterministically.
- ``bind_retry=False`` test mode keeps the constructor fast-failing.

Per-connection one-thread-per-handler is preserved for Phase 1; Phase 2 will
consolidate the accept loop onto ``selectors`` (or asyncio in Phase 1.5).
"""

from __future__ import annotations

import logging
import socket
import threading
import time
from typing import Optional, Tuple

from s2c.framing import Framer, MessageSizeExceededError, encode_line


log = logging.getLogger("s2c.server")


class Server:
    """TCP chat server. One thread per accepted connection."""

    BUFF_SIZE = 4096
    # Five peers per room — small enough to fit typical screen real estate
    # (one header line + four ASCII cards) and large enough for ad-hoc chats
    # without exhausting file descriptors on the server side.
    MAX_ROOM_PEERS = 5

    def __init__(
        self,
        port: int,
        *,
        bind_retry: bool = True,
        max_message_size: int = Framer.DEFAULT_MAX_MESSAGE_SIZE,
    ) -> None:
        self.requested_port = port
        self.ip = "0.0.0.0"
        self.bind_retry = bind_retry
        self.max_message_size = max_message_size

        # rooms: {session_id: {client_id: {"c": socket}}}
        self.rooms: dict = {}
        self.lock = threading.Lock()
        self._workers_lock = threading.Lock()
        self._stop = threading.Event()
        self._workers: list[threading.Thread] = []
        self.sock = self._setup_socket()
        # If port == 0 the kernel assigned an ephemeral port; normalise.
        bound_addr = self.sock.getsockname()
        self.port = bound_addr[1]

    # ---- lifecycle ----------------------------------------------------------

    def _setup_socket(self) -> socket.socket:
        """Bind + listen; retry forever unless :attr:`bind_retry` is False."""
        while True:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((self.ip, self.requested_port))
                sock.listen(64)
                return sock
            except OSError as exc:
                sock.close()
                if not self.bind_retry:
                    raise
                log.warning(
                    "Couldn't bind to %s:%s (%s); retrying in 1s",
                    self.ip,
                    self.requested_port,
                    exc,
                )
                time.sleep(1)

    def serve_forever(self) -> None:
        """Accept loop. Returns when :meth:`shutdown` unblocks accept()."""
        log.info("S2C server listening on %s:%s", self.ip, self.port)
        try:
            while not self._stop.is_set():
                try:
                    conn, addr = self.sock.accept()
                except OSError as exc:
                    if self._stop.is_set():
                        return
                    log.exception("accept() failed: %s", exc)
                    return
                self._spawn_handler(conn, addr)
        except Exception:
            log.exception("accept loop crashed")

    def _spawn_handler(self, conn: socket.socket, addr) -> None:
        """Spawn a per-connection handler and register it for join/cleanup.

        ``_runner`` retrieves the actual Thread via
        ``threading.current_thread()`` inside the worker so the cleanup path
        uses the real Thread identity. (An earlier draft tried to
        forward-reference the Thread via a walrus on
        ``Thread.__new__(Thread)``, which constructed an empty Thread
        *instance* but never the one that was actually started, so
        ``self._workers.remove(thread)`` always raised ``ValueError`` and
        finished silently — re-introducing the original memory leak.)
        """
        def _runner() -> None:
            thread = threading.current_thread()
            try:
                self._handle_client(conn, addr)
            finally:
                # Remove ourselves from _workers so completed handlers don't
                # accumulate (memory pressure during long-running servers).
                with self._workers_lock:
                    try:
                        self._workers.remove(thread)
                    except ValueError:
                        log.warning(
                            "worker %s not in _workers during cleanup",
                            thread.name,
                        )

        t = threading.Thread(
            target=_runner,
            daemon=True,
            name=f"s2c-handler-{addr[0]}:{addr[1]}",
        )
        with self._workers_lock:
            self._workers.append(t)
        t.start()

    def shutdown(self, timeout: float = 2.0) -> None:
        """Stop accepting, close every peer, join workers with timeout."""
        self._stop.set()
        try:
            self.sock.close()
        except OSError:
            pass
        with self.lock:
            for sid in list(self.rooms):
                for cid in list(self.rooms[sid]):
                    meta = self.rooms[sid][cid]
                    try:
                        meta["c"].close()
                    except OSError:
                        pass
            self.rooms.clear()
        for t in list(self._workers):
            t.join(timeout=timeout)
        self._workers.clear()

    # ---- peer management ----------------------------------------------------

    def _save_peer(self, sid: str, cid: str, conn: socket.socket) -> bool:
        """Register ``(sid, cid)`` if room has capacity. Idempotent.

        Returns ``False`` when the room is already at :attr:`MAX_ROOM_PEERS`.
        Only creates the room entry when the candidate will actually be
        admitted — avoids leaking empty placeholder rooms.
        """
        with self.lock:
            room = self.rooms.get(sid)
            if room is not None and cid in room:
                return True
            if room is not None and len(room) >= self.MAX_ROOM_PEERS:
                return False
            if room is None:
                room = {}
                self.rooms[sid] = room
            room[cid] = {"c": conn}
            return True

    def _remove_peer(
        self, sid: str, cid: str, conn: socket.socket
    ) -> Optional[socket.socket]:
        """Atomically pop ``(sid, cid)`` if it still maps to ``conn``.

        Returns the popped socket so the caller can close it OUTSIDE the lock
        (avoids holding the room lock over a blocking close()). Idempotent.
        """
        with self.lock:
            room = self.rooms.get(sid)
            if room is None:
                return None
            meta = room.get(cid)
            if meta is None:
                return None
            if meta.get("c") is not conn:
                return None
            sock = meta["c"]
            del room[cid]
            if not room:
                del self.rooms[sid]
            return sock

    def _find_and_remove(self, conn: socket.socket) -> None:
        """Remove ``conn`` from whatever room it lives in, if any. Idempotent."""
        with self.lock:
            for sid in list(self.rooms):
                room = self.rooms[sid]
                for cid in list(room):
                    if room[cid].get("c") is conn:
                        del room[cid]
                        if not room:
                            del self.rooms[sid]
                        return

    def _broadcast(self, sender: socket.socket, sid: str, raw: bytes) -> None:
        """Fan-out ``raw`` (already '\\n' terminated) to every peer in ``sid``.

        Collects send failures while holding the lock, then releases the lock
        before removing the failed peer — this guarantees the rooms dict is
        never mutated while another thread iterates it.
        """
        to_remove: list[Tuple[str, str, socket.socket]] = []
        with self.lock:
            room = self.rooms.get(sid)
            if not room:
                return
            # Snapshot so concurrent deletes don't break iteration.
            for cid, meta in list(room.items()):
                conn = meta.get("c")
                if conn is None or conn is sender:
                    continue
                try:
                    conn.sendall(raw)
                except OSError as exc:
                    log.debug(
                        "send to %s/%s failed: %s — scheduling cleanup",
                        sid,
                        cid,
                        exc,
                    )
                    to_remove.append((sid, cid, conn))
        for sid, cid, conn in to_remove:
            sock = self._remove_peer(sid, cid, conn)
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

    # ---- per-connection loop -----------------------------------------------

    def _handle_client(self, conn: socket.socket, addr) -> None:
        framer = Framer(max_message_size=self.max_message_size)
        log.debug("client connected: %s", addr)
        try:
            while not self._stop.is_set():
                try:
                    chunk = conn.recv(self.BUFF_SIZE)
                except OSError:
                    break
                if not chunk:
                    break
                try:
                    frames = framer.feed(chunk)
                except MessageSizeExceededError as exc:
                    log.warning(
                        "closing %s — oversized frame: %s", addr, exc,
                    )
                    break
                for pkt in frames:
                    self._route_frame(pkt, conn)
        except Exception:
            log.exception("handler error for %s", addr)
        finally:
            self._find_and_remove(conn)
            # Half-close before close(): queueing FIN via shutdown(SHUT_WR)
            # lets the kernel deliver a clean connection-end to the peer so
            # they see `recv() == b""` instead of an RST
            # (`ConnectionResetError`). Mirrors how SSH / postgres do on
            # error disconnects — better protocol citizenship.
            try:
                conn.shutdown(socket.SHUT_WR)
            except OSError:
                pass
            try:
                conn.close()
            except OSError:
                pass
            log.debug("client disconnected: %s", addr)

    def _route_frame(self, pkt: dict, conn: socket.socket) -> None:
        """Decode one valid NDJSON frame into the right internal action.

        Contract (Phase 1):
        * Any packet with both ``i`` (client_id) and ``s`` (session_id)
          REGISTERS the peer. This makes future control frames (presence,
          mute-tell, heartbeat — Phase 3) trivially extensible without
          changing the registration path.
        * Only packets with an audio or video payload (``v`` or ``a`` key)
          are BROADCAST to the other peers.
        * Drop silently on protocol violations (missing keys) — never crash
          the handler for a single bad frame.
        """
        sid = pkt.get("s")
        cid = pkt.get("i")
        if not sid or not cid:
            return
        if not self._save_peer(sid, cid, conn):
            log.debug("room %s full; dropping frame from %s", sid, cid)
            return
        if "v" not in pkt and "a" not in pkt:
            # registration-only frame; nothing to broadcast — but log so
            # control frames (presence/mute-tell/heartbeat in Phase 3) surface
            # in observability when they arrive.
            log.debug("registration-only frame from %s/%s (no v/a)", sid, cid)
            return
        raw = encode_line(pkt)
        self._broadcast(conn, sid, raw)


def main(argv: Optional[list] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="s2c_server")
    parser.add_argument(
        "-p", "--port", type=int, default=1122, help="Listening port",
    )
    parser.add_argument(
        "-v", "--verbose", action="count", default=0,
        help="Increase logging verbosity (repeatable).",
    )
    args = parser.parse_args(argv)
    level = logging.WARNING - 10 * min(args.verbose, 2)
    logging.basicConfig(
        level=max(level, logging.DEBUG),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    server = Server(args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt received, shutting down…")
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
