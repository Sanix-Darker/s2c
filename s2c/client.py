import json, socket, threading, pyaudio
import time
import base64
from os import (
        path as os_path,
        name as os_name,
        system
)
from s2c.settings import *
from cv2 import (
        resize,
        flip,
        cvtColor,
        COLOR_BGR2GRAY,
        VideoCapture
)
from s2c.utils.camera import ascii_it
from s2c.utils.helpers import get_trace



class Client:
    def __init__(self, session):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ip = session["ip"]
        self.port = session["port"]

        self.session_key = session["session_key"]
        self.session_id = session["session_id"]
        self.client_id = session["client_id"]

        self.size = [50, 15]
        self.faces = {}

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
        rate = 10000

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

        self.start_logs()

        # start threads
        receive_thread = threading.Thread(target=self.receive_server_data).start()
        threading.Thread(target=self.send_audio_to_server).start()
        threading.Thread(target=self.print_faces).start()
        self.send_frame_to_server()

    def start_logs(self):
        """
        Just the starting logs

        """
        system('cls' if os_name == 'nt' else 'clear')
        print("[-] s2c started...")
        print(f"[>] session_id : {self.session_id}")
        print(f"[<] client_id : {self.client_id}")
        print(f"[:] session_key : {self.session_key}")
        print("[-] Connected to Server")

    def print_faces(self):
        """
        Just to print faces from the self.faces

        """
        while True:
            system('cls' if os_name == 'nt' else 'clear')
            print("-" * 30)
            print(f"[+] s2c v{version} | session_id : {self.session_id}")
            print("-" * 30)

            to_print = ""
            to_print2 = ""
            for i in range(15):
                try:
                    for index, f in enumerate(self.faces):
                        if index < 3:
                            if f not in to_print:
                                to_print += "client_id: " + f + "\n"
                            to_print += self.faces[f].split("\n")[i] + " | "
                        else:
                            if f not in to_print:
                                to_print += "client_id: " + f + "\n"
                            to_print2 += self.faces[f].split("\n")[i] + " | "

                    to_print += "\n"
                    if len(self.faces) > 3:
                        to_print2 += "\n"

                except Exception as es:
                    pass

            print(to_print)
            print("\n" + "-"*30)
            print(to_print2)

    def receive_server_data(self):
        """
        This method is responsible on receiving the video and the audio
        """
        # print("[+] receiver's Thread started...")

        while True:
            received_msg = self.s.recv(2048)
            try:
                received_msg = json.loads(received_msg.decode("utf-8"))

                if "a" in received_msg:
                    audio_chunk = base64.b64decode(received_msg["a"])
                    self.playing_stream.write(audio_chunk)

                if "v" in received_msg:
                    self.faces[received_msg["i"]] = received_msg["v"]

            except (Exception, json.decoder.JSONDecodeError) as es:
                get_trace()

    def send_audio_to_server(self):
        """
        This method will send audio in a seperate thread

        """
        # print("[+] Audio sender's Thread started...")

        while True:
            try:
                # We get the audio stream (1024 in size)
                audio_data = self.recording_stream.read(512)

                # We send the audio tape
                audio_tape = json.dumps({
                    "i": self.client_id,
                    "s": self.session_id,
                    "a": base64.b64encode(audio_data).decode("utf-8")
                })

                try:
                    self.s.sendall(bytes(audio_tape, encoding="utf-8"))
                except ConnectionResetError as es:
                    get_trace()
            except KeyboardInterrupt as es:
                self.cam.release()
                break

    def send_frame_to_server(self):
        """
        This method will send the frames in a while Loop

        """
        while True:
            try:
                _, img = self.cam.read()
                if _:
                    # We enerate our ascii frame
                    ascii_frame = ascii_it(
                                self.client_id,
                                self.session_id,
                                flip(resize(img, (self.size[0], self.size[1])),1))

                    # We send the frame
                    frame = json.dumps({
                        "i": self.client_id,
                        "s": self.session_id,
                        "v": ascii_frame
                    })
                    # We add our self's fce in the faces object
                    self.faces[self.client_id] = ascii_frame
                    try:
                        # We send through sockets
                        self.s.sendall(bytes(frame, encoding="utf-8"))
                    except ConnectionResetError as es:
                        get_trace()
            except KeyboardInterrupt as es:
                self.cam.release()
                break

