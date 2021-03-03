from bisect import bisect
from app.settings import *

from cv2 import (
        resize,
        flip,
        cvtColor,
        COLOR_BGR2GRAY,
        VideoCapture
)
from os import name as os_name, system
from hashlib import sha256



def pretty_print_frame(client_id: str, session_id: str, string: str):
    """
    Just a simple a method to pretty print a ascii
    frame with more infos

    """

    # We make sure to have something in the string
    # before printing it
    if len(string) > 3:
        size = str(len(string.split("\n")[0])) + " x " + str(string.count("\n"))
        system('cls' if os_name == 'nt' else 'clear')
        print("-" * 50)
        print("[+] s2c v{} | session_id : {} | size : {}".format(version, session_id, size))
        print("-" * 50)
        print(string)
        print("-" * 50)
        print("client_id : {} | raw : {}".format(client_id, str(len(string))))
        print("-" * 50)


def generate_frame(client_id, session_id, fps_str, gray_image, characters, indices):
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

    # pretty_print_frame(client_id, session_id, string)

    return string


def get_fps(frames):
    """
    Jut to get the frame per second count

    """
    fps = int(frames // (time.time() - start))

    return '  {} FPS'.format(fps)


def ascii_it(client_id, session_id, image):
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

    return generate_frame(client_id, session_id, fps_str, gray_image, characters, indices)


###################################################################################################

