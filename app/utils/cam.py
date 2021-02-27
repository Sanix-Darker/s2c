from cv2 import resize, flip, cvtColor, COLOR_BGR2GRAY, VideoCapture
from bisect import bisect
import time
from hashlib import sha256
from os import system, name as os_name, path
from app.settings import (
    version,
    characters,
    global_brightnesses,
    client,
    start,
    frames,
    indices,
    key_path,
    passphrase
)
from app.utils.pgp import (
    import_keys,
    generate_pub_priv_keys,
    encrypt,
    decrypt
)

import socket



HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 65432        # Port to listen on (non-privileged ports are > 1023)


def pretty_print_frame(string: str):
    """

    """
    system('cls' if os_name == 'nt' else 'clear')

    print("-" * 70)
    print("[+] s2c v{} | Client : {}".format(version, client))
    print("-" * 70)
    print(string)
    print("-" * 70)
    print(sha256(string.encode()).hexdigest() + " |" + str(len(string)))
    print("-" * 70)



def generate_frame(fps_str, gray_image, characters, indices, gpg, ks):
    """
    This method will print the ASCII frame and return the encrypted
    frame using PGP encryption

    Args:
        - fps_str,
        - gray_image,
        - characters,
        - indices,
        - gpg,
        - ks
    """

    string = ''
    for row in gray_image:
        for c in row:
            string += characters[indices[c]]
        string += '\n'
    string = string[:-len(fps_str) - 1] + fps_str

    pretty_print_frame(string)

    return string
    # return encrypt(gpg, string, recipients=ks)


def get_fps(frames):
    elapsed = time.time() - start
    fps = int(frames / elapsed)
    return '  {} FPS'.format(fps)


def ascii_it(image, gpg, ks):
    """
    From an image to an ASCII representation with brightnesses

    """

    global frames

    # Convert to grayscale
    gray_image = 255 - cvtColor(image, COLOR_BGR2GRAY)

    # Normalize so that the whole range of characters is used
    upper_limit = gray_image.max() * ((len(characters) + 1) / float(len(characters)))
    lower_limit = gray_image.min()

    bright_div = (global_brightnesses - global_brightnesses.min()) / (
                global_brightnesses.max() - global_brightnesses.min())
    brightnesses = bright_div * (upper_limit - lower_limit) + lower_limit

    frames += 1
    fps_str = get_fps(frames)

    for c in range(gray_image.min(), gray_image.max() + 1):
        indices[c] = bisect(brightnesses, c)

    return generate_frame(fps_str, gray_image, characters, indices, gpg, ks)


def start_cam(gpg, ser):

    # We check if the key is present
    # if not we generate a key pair
    if not path.exists(key_path):
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

                        time.sleep(0.05)
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
                        received = conn.recv(3000).decode()
                        if len(received) > 30:
                            pretty_print_frame(received)
                            # print(decrypt(gpg, received, passphrase))
                    except KeyboardInterrupt as es:
                        break

###################################################################################################

