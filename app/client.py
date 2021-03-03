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

        while True:
            try:
                self.s.connect((self.ip, self.port))

                break
            except:
                print("[x] Couldn't connect to server {}:{}".format(str(self.ip), str(self.port)))
                time.sleep(1)

        # The Cature for cam
        self.cam = VideoCapture(0)
        self.cam.set(3, 25)
        self.cam.set(4, 70)

        chunk_size = 1024 # 512
        audio_format = pyaudio.paInt16
        channels = 1
        rate = 20000

        # initialise microphone recording
        self.p = pyaudio.PyAudio()
        self.playing_stream = self.p.open(format=audio_format, channels=channels, rate=rate, output=True, frames_per_buffer=chunk_size)
        self.recording_stream = self.p.open(format=audio_format, channels=channels, rate=rate, input=True, frames_per_buffer=chunk_size)

        print("[-] Connected to Server")

        # start threads
        receive_thread = threading.Thread(target=self.receive_server_data).start()
        self.send_data_to_server()

    def receive_server_data(self):

        while True:
            try:
                received_msg = self.recv(3072).decode("utf-8")
                if len(received_msg) > 30:
                    received_msg = json.loads(received_msg)
                    decoded_msg = {
                        "i": self.client_id,
                        "s": self.session_id,
                        "v": decrypt_aes(
                                self.session_key,
                                received_msg["v"]),
                        "a": decrypt_aes(
                                self.session_key,
                                received_msg["a"])
                    }

                    self.playing_stream.write( decoded_msg["a"]["r"].encode().decode('ascii') )
                    pretty_print_frame( decoded_msg["v"].decode("utf-8") )
            except:
                pass


    def send_data_to_server(self):
        while True:
            try:
                _, img = self.cam.read()
                if _:
                    # We get the audio stream (1024 in size)
                    audio_data = self.recording_stream.read(1024)

                    to_send = json.dumps({
                        "i": self.client_id,
                        "s": self.session_id,
                        "v": encrypt_aes(
                                self.session_key,
                                ascii_it(flip(resize(img, (70, 25)),1))).decode(),
                        "a": encrypt_aes(
                                self.session_key,
                                json.dumps({"r": base64.b64encode(audio_data).decode()})).decode()
                    })

                    self.s.sendall(bytes(to_send,encoding="utf-8"))
            except KeyboardInterrupt as es:
                cam.release()
                break

