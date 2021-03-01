import socket, time

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



def client(s, kripta_aes, session):
    """
    This method will start the video camera
    and send the encrypted ascii version throught sockets

    """

    # The Cature for cam
    cam = VideoCapture(0)
    cam.set(3, 25)
    cam.set(4, 70)

    s.connect((session["host"], session["port"]))
    while True:
        try:
            _, img = cam.read()
            if _:
                s.sendall(
                    encrypt_aes(
                        kripta_aes,
                        session["key"],
                        ascii_it(
                            flip(resize(img, (70, 25)),1)
                        )
                    )
                )
                time.sleep(0.05)
        except KeyboardInterrupt as es:
            cam.release()
            break


def server(s, kripta_aes, session):
    """
    This method should send the request to start a new session

    """

    # am the server
    s.bind((session["host"], session["port"]))
    s.listen()

    conn, addr = s.accept()
    with conn:
        print('Connected by', addr)
        while True:
            try:
                received_msg = conn.recv(3500).decode("utf-8")
                if len(received_msg) > 30:
                    pretty_print_frame(
                        decrypt_aes(
                            kripta_aes,
                            session["key"],
                            received_msg
                        ).decode("utf-8")
                    )
            except KeyboardInterrupt as es:
                break


def run(kripta_aes: object, session: object):

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Am the client
        if session["status"] == "join":
            client(s, kripta_aes, session)
        elif session["status"] == "create":
            server(s, kripta_aes, session)
        else:
            print("[x] Any valuable information provided !")
            print("-"*70)

