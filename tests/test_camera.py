import pytest
import numpy as np
import cv2
import os
from pytest_mock import MockerFixture
from s2c.utils.camera import ascii_it, generate_frame


@pytest.fixture
def sample_fps_str() -> str:
  return "30 fps"

@pytest.fixture
def sample_gray_image() -> list:
    return [
        [0, 1, 120],
        [3, 40, 15],
        [200, 7, 80]
    ]

# -- genererate_frame test

# Test case: Basic functionality
def test_generate_frame_basic(sample_fps_str: str, sample_gray_image: list) -> None:
    expected_result = (
        " M M M \n"
        " M M M \n"
        " M M M \n"
        ">30 fps"
    )
    result = generate_frame(sample_fps_str, sample_gray_image)
    assert result == expected_result

# Test case: Empty gray_image
def test_generate_frame_empty_gray_image(sample_fps_str: str) -> None:
    sample_empty_image = []
    expected_result = " >30 fps"
    result = generate_frame(sample_fps_str, sample_empty_image)
    assert result == expected_result

# Test case: Empty fps_str
def test_generate_frame_empty_fps_str(sample_gray_image: list) -> None:
    sample_empty_fps = ""
    expected_result = (
       " M M M \n"
       " M M M \n"
       " M M M \n"
       ">"
    )
    result = generate_frame(sample_empty_fps, sample_gray_image)
    assert result == expected_result

# Test case: Gray image with special characters
def test_generate_frame_special_characters(sample_fps_str: str) -> None:
    sample_special_image = [
        [10, 11, 12],
        [13, 14, 15],
        [16, 17, 18]
    ]
    expected_result = (
       " M M M \n"
       " M M M \n"
       " M M M \n"
       ">30 fps"
    )
    result = generate_frame(sample_fps_str, sample_special_image)
    assert result == expected_result


# -- ascii_it tests
# Define a test case for the ascii_it function
def test_ascii_it(mocker: MockerFixture) -> None:
    mocker.patch('s2c.utils.camera.generate_frame', return_value=(
       " M M M \n"
       " M M M \n"
       " M M M \n"
       ">30 fps"
    ))

    # Load a fixture image using OpenCV
    opencv_image = cv2.imread(os.path.join('tests/fixture.png'))
    result = ascii_it("client_id", "session_id", np.array(opencv_image))

    # You should define expected_result based on your knowledge of the function's behavior
    expected_result = (
       " M M M \n"
       " M M M \n"
       " M M M \n"
       ">30 fps"
    )

    assert result == expected_result
