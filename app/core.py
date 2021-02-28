import socket
import time
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
        import_keys,
        ascii_it,
        generate_pub_priv_keys
)
from app.utils.pgp import (
        import_keys,
        generate_pub_priv_keys,
        encrypt,
        decrypt
)



def run(gpg, ser):

    # We check if the key is present
    # if not we generate a key pair
    if not os_path.exists(key_path):
        generate_pub_priv_keys(gpg, key_path, passphrase)

    # We import keys pair from the file saved locally
    ks = import_keys(gpg, key_path)

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
                        encrypted_frame = ascii_it(flip(resize(img, (70, 25)), 1), gpg, ks)
                        s.sendall(encrypted_frame.encode())

                        time.sleep(0.3)
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
                        received = conn.recv(3500).decode()
                        if len(received) > 30:
                            pretty_print_frame(decrypt(gpg, received, passphrase))
                            # print(decrypt(gpg, received, passphrase))
                    except KeyboardInterrupt as es:
                        break


