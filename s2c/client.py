import socket
import threading
import pyaudio
import time
import base64
import json
import os
from cv2 import (
    resize,
    flip,
    VideoCapture,
    cvtColor,
    COLOR_BGR2GRAY,
)
import numpy as np

from bisect import bisect

# To prevent ruff spreading these two arrays
# fmt: off
CHARACTERS = [ "M", "B", "N", "W", "R", "g", "#", "Q", "8", "D", "$", "0", "H", "@", "m", "&", "E", "O", "9", "6", "d", "b", "A", "p", "K", "q", "Z", "G", "U", "X", "P", "5", "a", "2", "S", "k", "e", "h", "4", "V", "3", "I", "w", "F", "y", "o", "{", "}", "f", "C", "u", "n", "1", "z", "%", "s", "t", "x", "Y", "J", "[", "T", "]", "j", "7", "L", "i", "l", "v", "c", "?", ")", "(", "/", "r", "<", ">", "*", "=", "|", "+", "!", "_", ";", "^", ":", "~", ",", ".", "-", "`", " ", ]
GLOBAL_BRIGHTNESSES = np.array( [ 156.1, 157.6, 159.9, 160.6, 164.8, 165.6, 166.3, 167.1, 168.9, 169.9, 171.2, 171.6, 172.1, 172.2, 172.4, 173.5, 173.7, 173.9, 173.9, 174.0, 174.7, 174.7, 174.9, 176.3, 176.3, 176.4, 176.7, 177.4, 179.2, 179.5, 179.6, 180.0, 181.2, 181.4, 182.1, 182.2, 182.3, 184.6, 184.9, 185.7, 186.7, 188.1, 189.1, 189.7, 192.0, 192.3, 194.5, 194.5, 195.1, 195.7, 195.7, 195.8, 196.0, 196.3, 196.7, 196.8, 197.9, 198.6, 198.7, 198.9, 199.2, 199.2, 199.2, 200.0, 200.5, 202.4, 202.4, 203.3, 203.9, 205.9, 208.9, 214.7, 214.8, 215.2, 215.5, 215.8, 215.8, 220.8, 223.1, 223.1, 225.2, 225.6, 229.5, 230.5, 231.7, 238.0, 238.7, 239.0, 246.5, 246.5, 248.3, 255.0, ])
# fmt: on

INDICES = [0] * 256

FRAMES = 0
START = time.time()


class Client:
    CHUNK = 512
    RATE = 10_000
    SIZE = (60, 20)  # for less ascii generated items to broadcast

    def __init__(self, session):
        self.session = session
        self.session_key = session["session_key"]
        self.session_id = session["session_id"]
        self.client_id = session["client_id"]

        self.faces = {}
        self.lock = threading.Lock()

        self._connect()
        self._setup_media()
        self._start_threads()

        self._send_frames()

    def _connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        while self.sock.connect_ex((self.session["ip"], self.session["port"])) != 0:
            time.sleep(1)

    def _setup_media(self):
        self.cam = VideoCapture(0)
        self.cam.set(3, self.SIZE[0])
        self.cam.set(4, self.SIZE[1])

        p = pyaudio.PyAudio()
        self.play_stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.RATE,
            output=True,
            frames_per_buffer=self.CHUNK,
        )
        self.rec_stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK,
        )

    def _start_threads(self):
        """
        We have 3 threads here :
        - one for the permanant receiving of the whole broadcast's session
        - one for sending the audio
        - one for rendering all faces

        (to simulate the parralelism)
        """

        print("[-] s2c started...")
        print(f"[>] session_id : {self.session_id}")
        print(f"[<] client_id : {self.client_id}")
        print(f"[:] session_key : {self.session_key}")
        print("[-] Connected to Server\n")

        threading.Thread(target=self._recv_data, daemon=True).start()
        threading.Thread(target=self._send_audio, daemon=True).start()
        threading.Thread(target=self._render_faces, daemon=True).start()

    def _recv_data(self):
        while True:
            try:
                raw = self.sock.recv(4096)
                if not raw:
                    continue

                msg = json.loads(raw.decode())
                if "a" in msg:
                    self.play_stream.write(base64.b64decode(msg["a"]))
                if "v" in msg:
                    with self.lock:
                        self.faces[msg["i"]] = msg["v"]
            except Exception as excp:
                print(excp)
                break

    # for the audio
    def _send_audio(self):
        while True:
            try:
                chunk = self.rec_stream.read(self.CHUNK, exception_on_overflow=False)
                packet = json.dumps(
                    {
                        "i": self.client_id,
                        "s": self.session_id,
                        "a": base64.b64encode(chunk).decode(),
                    }
                )
                self.sock.sendall(packet.encode())
            except Exception as excp:
                print(excp)
                break

    # for the video
    def _send_frames(self):
        while True:
            try:
                ok, frame = self.cam.read()
                if not ok:
                    continue

                ascii_frame = self.ascii_it(flip(resize(frame, self.SIZE), 1))

                with self.lock:
                    self.faces[self.client_id] = ascii_frame

                packet = json.dumps(
                    {"i": self.client_id, "s": self.session_id, "v": ascii_frame}
                )
                self.sock.sendall(packet.encode())
            except KeyboardInterrupt:
                self.cam.release()
                break
            except Exception as excp:
                print(excp)

    def _render_faces(self):
        clear = "cls" if os.name == "nt" else "clear"
        while True:
            os.system(clear)
            print("-" * 30)
            print(f"[+] s2c | session_id : {self.session_id}")
            print("-" * 30)

            with self.lock:
                keys = list(self.faces)
                left, right = keys[:3], keys[3:]
                lines = {k: self.faces[k].split("\n")[: self.SIZE[1]] for k in keys}
                uid = {k: f"client_id: {k}" for k in keys}
                width = {
                    k: max(len(uid[k]), *(len(li) for li in lines[k])) for k in keys
                }

            def block(cols):
                rows = []
                for i in range(self.SIZE[1]):
                    parts = []
                    for k in cols:
                        cell = (
                            uid[k]
                            if i == 0
                            else (lines[k][i] if i < len(lines[k]) else "")
                        )
                        parts.append(cell.ljust(width[k]))
                    if parts:
                        rows.append(" | ".join(parts))
                return "\n".join(rows)

            print(block(left))
            if right:
                print("\n" + "-" * 30)
                print(block(right))

            time.sleep(0.05)

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
        """
        From an image to an ASCII representation with brightnesses

        """
        global FRAMES

        # Convert to grayscale
        gray_image = 255 - cvtColor(image, COLOR_BGR2GRAY)

        # Normalize so that the whole range of characters is used
        upper_limit = gray_image.max() * (
            (len(CHARACTERS) + 1) / float(len(CHARACTERS))
        )
        lower_limit = gray_image.min()

        bright_div = (GLOBAL_BRIGHTNESSES - GLOBAL_BRIGHTNESSES.min()) / (
            GLOBAL_BRIGHTNESSES.max() - GLOBAL_BRIGHTNESSES.min()
        )
        brightnesses = bright_div * (upper_limit - lower_limit) + lower_limit

        FRAMES += 1
        fps_str = self.get_fps(FRAMES)

        for c in range(gray_image.min(), gray_image.max() + 1):
            INDICES[c] = bisect(brightnesses, c)

        return self.generate_frame(fps_str, gray_image, CHARACTERS, INDICES)
