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
from app.utils.cam import (
        pretty_print_frame,
        ascii_it
)
from app.utils.aes import (
        encrypt_aes,
        decrypt_aes
)



def run(kripta_aes: object, session: object):

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Am the client
        if ser == "-":
            # The Cpature for cam
            cam = VideoCapture(0)
            cam.set(3, 25)
            cam.set(4, 70)

            s.connect((HOST, PORT))
            while True:
                try:
                    _, img = cam.read()
                    if _:
                        s.sendall(
                            encrypt_aes(
                                kripta_aes,
                                ascii_it(
                                    flip(resize(img, (70, 25)),1)
                                ),key
                            )
                        )
                        time.sleep(0.1)
                except KeyboardInterrupt as es:
                    cam.release()
                    break
        else:
            # am the server
            s.bind((HOST, PORT))
            s.listen()

            conn, addr = s.accept()
            with conn:
                print('Connected by', addr)
                while True:
                    try:
                        received = conn.recv(3500)
                        if len(received) > 30:
                            pretty_print_frame(
                                decrypt_aes(
                                    kripta_aes,
                                    received.decode("utf-8"), key
                                ).decode("utf-8")
                            )
                    except KeyboardInterrupt as es:
                        break


