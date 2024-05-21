from bisect import bisect
from typing import Any
from functools import lru_cache
import time

from cv2 import (
    cvtColor,
    COLOR_BGR2GRAY,
)

from s2c.settings import BRIGHTNESS, CHARACTER_FILL

# some nice weird globlas
_FRAMES = 0
_START = time.time()
# FIXME: this makes no sense, i need to remove it at the first place !
_INDICES = [0] * 256


@lru_cache(maxsize=16)
def fill_character(c: int|str) -> str:

    global _INDICES

    try:
        assert isinstance(c, int)
        return CHARACTER_FILL[_INDICES[c]]
    except (TypeError, AssertionError):
        # supposully will be '\n' but just in case
        # I cast string it
        return str(c)

def generate_frame(fps_str: str, gray_image: Any) -> str:
    """
    This method will print the ASCII frame
    """

    # Some list comprehension here to speedup the frame generation per row
    # we print the frame and the fps appended to it
    return ' ' + ' '.join(
        [fill_character(c) for row in gray_image for c in row + ['\n']]
    ) +  f'>{fps_str}'

def get_fps(client_id: str, session_id: str, frames: int) -> str:
    """
    Jut to get the frame per second count

    """
    return f"{client_id}/{session_id}  {frames // (time.time() - _START)} FPS"


def ascii_it(client_id: str, session_id: str, image: Any) -> str:
    """
    From an image to an ASCII representation with brightnesses

    """

    global _FRAMES, _INDICES

    # Convert to grayscale
    gray_image = 255 - cvtColor(image, COLOR_BGR2GRAY)

    character_fill_len = len(CHARACTER_FILL)
    # Normalize so that the whole range of characters is used
    upper_limit = gray_image.max() * (
        (character_fill_len + 1) / character_fill_len
     )
    lower_limit = gray_image.min()

    bright_div = (BRIGHTNESS - BRIGHTNESS.min()) / (BRIGHTNESS.max() - BRIGHTNESS.min())
    brightnesses = bright_div * (upper_limit - lower_limit) + lower_limit

    _FRAMES += 1
    fps_str = get_fps(client_id, session_id, _FRAMES)

    for c in range(gray_image.min(), gray_image.max() + 1):
        _INDICES[c] = bisect(brightnesses, c)

    frame_generated = generate_frame(
        fps_str,
        gray_image,
    )

    return frame_generated
