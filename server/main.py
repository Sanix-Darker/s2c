import socket
import argparse
import threading
import json
import time
from threading import Lock


class Server:
    BUFF_SIZE = 4096

    def __init__(self, port: int):
        self.ip, self.port = "0.0.0.0", port
        self.rooms: dict[str, dict] = (
            {}
        )  # {session_id: {"d": last_seen_ts, client_id: {"c": sock}}}
        self.lock = Lock()
        self._setup_socket()

    def _setup_socket(self) -> None:
        """Bind & listen, retrying until the port becomes free."""
        while True:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.sock.bind((self.ip, self.port))
                self.sock.listen()
                break
            except OSError as e:
                print(f"[x] Couldn't bind to port {self.port}: {e}; retrying…")
                time.sleep(1)

    def _save_room(self, conn: socket.socket, pkt: dict) -> None:
        """Register (session_id, client_id) pair and keep max 5 peers per room."""
        sid, cid = pkt["s"], pkt["i"]
        with self.lock:
            room = self.rooms.setdefault(sid, {"d": time.time()})
            if cid not in room and len(room) < 6:  # 5 peers + "d"
                room[cid] = {"c": conn}

    def _broadcast(self, sender: socket.socket, pkt: dict) -> None:
        """Forward pkt to every peer in the room except sender."""
        self._save_room(sender, pkt)

        sid = pkt["s"]
        with self.lock:
            room = self.rooms[sid]
            room["d"] = time.time()
            payload = json.dumps(pkt).encode()

            for meta in room.values():
                if isinstance(meta, socket.socket):
                    conn = meta
                elif isinstance(meta, dict):
                    conn = meta.get("c", None)
                else:
                    continue

                if not conn or conn is sender:
                    continue

                try:
                    conn.sendall(payload)
                except Exception as excp:
                    print(excp)

    def _handle_client(self, conn: socket.socket) -> None:
        try:
            while True:
                raw = conn.recv(self.BUFF_SIZE)
                if not raw:
                    break
                try:
                    pkt = json.loads(raw.decode())
                    if "i" in pkt and "s" in pkt:
                        self._broadcast(conn, pkt)
                except json.JSONDecodeError:
                    # should probably log here... but boff...
                    continue
        except Exception as excp:
            print(excp)
        finally:
            conn.close()

    # entrypoint
    def serve_forever(self) -> None:
        print("[-] S2C server started...")
        print(f"[-] Running on {self.ip}:{self.port}")

        while True:
            conn, _ = self.sock.accept()
            threading.Thread(
                target=self._handle_client, args=(conn,), daemon=True
            ).start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=1122, help="Listening port")
    args = parser.parse_args()

    Server(args.port).serve_forever()
