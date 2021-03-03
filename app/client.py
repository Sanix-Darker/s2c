import json, socket, threading, pyaudio
import time
import base64

from os import path as os_path
from app.settings import *

from cv2 import (
        resize,
        flip,
        cvtColor,
        COLOR_BGR2GRAY,
        VideoCapture
)
from app.utils.camera import (
        pretty_print_frame,
        ascii_it
)
from app.utils.helpers import get_trace

from app.modules.security.aes import (
        encrypt_aes,
        decrypt_aes
)



class Client:
    def __init__(self, session):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ip = session["ip"]
        self.port = session["port"]

        self.session_key = session["session_key"]
        self.session_id = session["session_id"]
        self.client_id = session["client_id"]

        self.size = [35, 11]

        while True:
            try:
                self.s.connect((self.ip, self.port))

                break
            except:
                print("[x] Couldn't connect to server {}:{}".format(str(self.ip), str(self.port)))
                time.sleep(1)

        # The Cature for cam
        self.cam = VideoCapture(0)
        self.cam.set(2, self.size[1])
        self.cam.set(3, self.size[0])

        chunk_size = 1024
        audio_format = pyaudio.paInt16
        channels = 1
        rate = 20000

        # initialise microphone recording
        self.p = pyaudio.PyAudio()
        self.playing_stream = self.p.open(
                format=audio_format,
                channels=channels,
                rate=rate,
                output=True,
                frames_per_buffer=chunk_size
        )
        self.recording_stream = self.p.open(
                format=audio_format,
                channels=channels,
                rate=rate,
                input=True,
                frames_per_buffer=chunk_size
        )

        print("[-] Connected to Server")

        # start threads
        receive_thread = threading.Thread(target=self.receive_server_data).start()
        self.send_data_to_server()

    def receive_server_data(self):

        while True:
            try:
                received_msg = self.s.recv(3072)

                if len(received_msg.decode("utf-8")) > 30:
                    try:
                        received_msg = json.loads(received_msg.decode("utf-8"))

                        if "a" in received_msg:
                            audio_chunk = base64.b64decode(received_msg["a"]["r"])
                            self.playing_stream.write(audio_chunk)

                            silence = chr(0)*len(audio_chunk)*2

                            free = self.playing_stream.get_write_available() # How much space is left in the buffer?
                            if free > len(audio_chunk): # Is there a lot of space in the buffer?
                                tofill = free - len(audio_chunk)
                                self.playing_stream.write(silence * tofill) # Fill it with silence

                        # if "v" in received_msg:
                        #    pretty_print_frame(received_msg["i"], received_msg["s"], received_msg["v"] )
                    except json.decoder.JSONDecodeError as es:
                        pass
            except Exception as es:
                get_trace()

    def send_data_to_server(self):
        while True:
            try:
                _, img = self.cam.read()
                if _:
                    # We get the audio stream (1024 in size)
                    audio_data = self.recording_stream.read(1024)
                    # We send the frame
                    to_send = json.dumps({
                        "i": self.client_id,
                        "s": self.session_id,
                        "v": ascii_it(self.client_id, self.session_id, flip(resize(img, (self.size[0], self.size[1])),1)),
                        "a": {"r": base64.b64encode(audio_data).decode("utf-8")}
                    })
                    try:
                        self.s.sendall(bytes(to_send,encoding="utf-8"))
                    except ConnectionResetError as es:
                        get_trace()
            except KeyboardInterrupt as es:
                self.cam.release()
                break

