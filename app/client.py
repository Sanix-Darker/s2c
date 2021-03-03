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

        self.size = [37, 11]

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

        chunk_size = 512
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
                received_msg = self.recv(4096).decode("utf-8")
                print("received_msg: ", received_msg)
                if len(received_msg) > 30:
                    received_msg = json.loads(received_msg)

                    audio_bin =  json.loads(received_msg["a"])["r"].encode().decode('ascii')
                    print("audio_bin : ", audio_bin)
                   # pretty_print_frame(received_msg["i"], received_msg["s"], received_msg["v"].decode("utf-8") )
                    self.playing_stream.write(audio_bin)
            except:
                pass


    def send_data_to_server(self):
        while True:
            try:
                _, img = self.cam.read()
                if _:
                    # We get the audio stream (1024 in size)
                    audio_data = self.recording_stream.read(512)

                    to_send = json.dumps({
                        "i": self.client_id,
                        "s": self.session_id,
                        "v": ascii_it(self.client_id, self.session_id, flip(resize(img, (self.size[0], self.size[1])),1)),
                        "a": json.dumps({"r": base64.b64encode(audio_data).decode()})
                    })
                    try:
                        self.s.sendall(bytes(to_send,encoding="utf-8"))
                    except ConnectionResetError as es:
                        time.sleep(1)
            except KeyboardInterrupt as es:
                self.cam.release()
                break

