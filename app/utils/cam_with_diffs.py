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
import json



HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 65432        # Port to listen on (non-privileged ports are > 1023)
CURRENT_ASCII_FRAME = ""
PRECEDENT_ASCII_FRAME = ""


def generate_frame(fps_str, gray_image, characters, indices):
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
    diffs = []

    for index, row in enumerate(gray_image):
        tmp_str = ""
        for c in row:
            tmp_str += characters[indices[c]]
        tmp_str += '\n'
        string += tmp_str

        # Here we are getting the approximate differences
        if len(CURRENT_ASCII_FRAME) != 0:
            diffs.append(get_diff(list(tmp_str), CURRENT_ASCII_FRAME.split("\n")[index]))
        else:
            diffs.append(get_diff(list(tmp_str), []))

    string = string[:-len(fps_str) - 1] + fps_str

    system('cls' if os_name == 'nt' else 'clear')

    print("[+] s2c v{} | Client : {}".format(version, client))

    print("-" * 70)
    print(string)
    print("-" * 70)
    print(sha256(string.encode()).hexdigest() + " |" + str(len(string)))
    print("-" * 70)
    print("size diffs : ", len(json.dumps(diffs)))

    return string, diffs


def get_fps(frames):
    """
    Get the FPS (Frame) per second am having here

    """
    elapsed = time.time() - start
    fps = int(frames / elapsed)
    return '  {} FPS'.format(fps)


def get_diff(list1, list2):
    """
    Get the difference between the first list and the second

    """
    diffs = []
    for index, (first, second) in enumerate(zip(list1, list2)):
        if first != second:
           diffs.append((index, second))

    return diffs


def ascii_it(image, gpg, ks):
    """
    From an image to an ASCII representation with brightnesses

    """

    global frames, CURRENT_ASCII_FRAME

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

    # We get our ascii frame generated
    # And the differences between the precedent frame
    ascii_frame, diffs = generate_frame(fps_str, gray_image, characters, indices)

    # We set the current ASCII-Frame as the ascii_frame generated if that value
    # was empty
    if len(CURRENT_ASCII_FRAME) == 0:
        CURRENT_ASCII_FRAME = ascii_frame

    return encrypt(gpg, json.dumps(diffs), recipients=ks)


def recompose(diffs):

    global PRECEDENT_ASCII_FRAME

    frame = ""
    if len(PRECEDENT_ASCII_FRAME) == 0:
        for d in diffs:
            for c in d:
                frame += c[1]
            frame += "\n"
        print("-- First")
    else:
        precedent_ascii_frame_arry = list(PRECEDENT_ASCII_FRAME.split("\n"))
#        for index_line, line in enumerate(precedent_ascii_frame_arry):
#            for index_character, c in enumerate(line):
        for index_line, d_line in enumerate(diffs):
            l = precedent_ascii_frame_arry[index_line]
            for d_character in d_line:
                for ii, c in enumerate(l):
                    if ii == d_character[0]:
                        frame += d_character[1]
                    else:
                        frame += c
            frame += "\n"

    PRECEDENT_ASCII_FRAME = frame

    print(PRECEDENT_ASCII_FRAME)


def start_cam(gpg, ser):

    # We check if the key is present
    # if not we generate a key pair
    if not path.exists(key_path):
        generate_pub_priv_keys(gpg, key_path, passphrase)

    # We import keys pair from the file saved locally
    ks = import_keys(gpg, key_path)

    current_ascii_frame = ""

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
                        encrypted = ascii_it(flip(resize(img, (70, 25)), 1), gpg, ks)
                        s.sendall(encrypted.encode())

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
                        received = conn.recv(3072).decode()
                        if len(received) > 30:
                            recompose(json.loads(decrypt(gpg, received, passphrase)))
                    except KeyboardInterrupt as es:
                        break

###################################################################################################

