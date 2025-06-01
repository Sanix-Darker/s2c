import pytest
import numpy as np
from client.main import Client, CHARACTERS, GLOBAL_BRIGHTNESSES, INDICES
from unittest.mock import MagicMock, patch
import time


@pytest.fixture
def sample_fps_str() -> str:
    return "30 FPS"


@pytest.fixture
def sample_gray_image() -> np.ndarray:
    return np.array([[0, 1, 120], [3, 40, 15], [200, 7, 80]], dtype=np.uint8)


@pytest.fixture
def mock_client() -> Client:
    session = {
        "session_id": "test_session",
        "client_id": "test_client",
        "session_key": "test_key",
        "ip": "127.0.0.1",
        "port": 2938,
    }
    client = Client(session)
    client.sock = MagicMock()
    client.cam = MagicMock()
    client.play_stream = MagicMock()
    client.rec_stream = MagicMock()
    return client


@pytest.fixture
def test_image() -> np.ndarray:
    # Create a simple 3x3 test image
    return np.array(
        [
            [[255, 255, 255], [0, 0, 0], [127, 127, 127]],
            [[0, 0, 0], [255, 255, 255], [127, 127, 127]],
            [[127, 127, 127], [0, 0, 0], [255, 255, 255]],
        ],
        dtype=np.uint8,
    )


# def test_generate_frame_basic(
#     mock_client: Client, sample_fps_str: str, sample_gray_image: np.ndarray
# ) -> None:
#     """Test frame generation with basic input"""
#     # Calculate expected indices
#     brightnesses = (
#         (GLOBAL_BRIGHTNESSES - GLOBAL_BRIGHTNESSES.min())
#         / (GLOBAL_BRIGHTNESSES.max() - GLOBAL_BRIGHTNESSES.min())
#         * 255
#     )
#     expected_chars = [
#         CHARACTERS[bisect(brightnesses, pixel)] for pixel in sample_gray_image.flatten()
#     ]
#
#     # Build expected string
#     expected = ""
#     for i in range(sample_gray_image.shape[0]):
#         row_start = i * sample_gray_image.shape[1]
#         row_end = row_start + sample_gray_image.shape[1]
#         expected += "".join(expected_chars[row_start:row_end]) + "\n"
#     expected = expected[: -len(sample_fps_str) - 1] + sample_fps_str
#
#     result = mock_client.generate_frame(
#         sample_fps_str, sample_gray_image, CHARACTERS, INDICES
#     )
#     assert result == expected
#
#
# def test_generate_frame_empty_image(mock_client: Client, sample_fps_str: str) -> None:
#     """Test with empty image array"""
#     empty_image = np.array([], dtype=np.uint8).reshape(0, 0)
#     result = mock_client.generate_frame(
#         sample_fps_str, empty_image, CHARACTERS, INDICES
#     )
#     assert result == sample_fps_str
#
#
# def test_get_fps(mock_client: Client) -> None:
#     """Test FPS calculation"""
#     global FRAMES, START
#     FRAMES = 0
#     START = time.time()
#
#     # Test initial FPS
#     fps_str = mock_client.get_fps(FRAMES)
#     assert "FPS" in fps_str
#     assert fps_str.endswith("FPS")
#
#     # Test after incrementing frames
#     FRAMES = 60
#     time.sleep(0.1)  # Ensure some time has passed
#     fps_str = mock_client.get_fps(FRAMES)
#     fps_value = int(fps_str.strip().split()[0])
#     assert fps_value > 0
#
#
# def test_ascii_it_conversion(mock_client: Client, test_image: np.ndarray) -> None:
#     """Test complete ASCII conversion pipeline"""
#     # Mock camera read
#     mock_client.cam.read.return_value = (True, test_image)
#
#     # Call ascii_it
#     result = mock_client.ascii_it(test_image)
#
#     # Verify basic structure
#     assert isinstance(result, str)
#     assert "\n" in result  # Should have multiple lines
#     assert "FPS" in result  # Should contain FPS counter
#
#     # Verify dimensions (3 rows + FPS line)
#     lines = result.split("\n")
#     assert len(lines) == 4  # 3 rows + FPS
#
#     # Verify each line has 3 characters (from our 3x3 test image)
#     for line in lines[:-1]:
#         assert len(line) == 3
#
#
# def test_ascii_it_edge_cases(mock_client: Client) -> None:
#     """Test edge cases in ASCII conversion"""
#     # Test with completely black image
#     black_image = np.zeros((3, 3, 3), dtype=np.uint8)
#     result = mock_client.ascii_it(black_image)
#     assert result.count(CHARACTERS[-1]) > 0  # Should use brightest character
#
#     # Test with completely white image
#     white_image = np.full((3, 3, 3), 255, dtype=np.uint8)
#     result = mock_client.ascii_it(white_image)
#     assert result.count(CHARACTERS[0]) > 0  # Should use darkest character
#
#
# def test_client_video_processing(mock_client: Client, test_image: np.ndarray) -> None:
#     """Test the complete video processing pipeline"""
#     # Setup mock camera to return our test image
#     mock_client.cam.read.return_value = (True, test_image)
#
#     # Mock socket send
#     with patch.object(mock_client.sock, "sendall") as mock_send:
#         mock_client._send_frames()
#
#         # Verify frame was processed and sent
#         assert mock_send.called
#         sent_data = mock_send.call_args[0][0].decode()
#         assert '"v"' in sent_data  # Should contain video data
#
#         # Verify our test client ID is in the sent data
#         assert mock_client.client_id in sent_data
#
#
# def test_client_audio_processing(mock_client: Client) -> None:
#     """Test audio processing pipeline"""
#     # Setup mock audio stream to return test data
#     test_audio = b"\x00\x01\x02\x03" * 128  # Simple test audio chunk
#     mock_client.rec_stream.read.return_value = test_audio
#
#     # Mock socket send
#     with patch.object(mock_client.sock, "sendall") as mock_send:
#         mock_client._send_audio()
#
#         # Verify audio was processed and sent
#         assert mock_send.called
#         sent_data = mock_send.call_args[0][0].decode()
#         assert '"a"' in sent_data  # Should contain audio data
#         assert base64.b64decode(json.loads(sent_data)["a"]) == test_audio
#
#
# def test_client_receive_processing(mock_client: Client) -> None:
#     """Test receive processing pipeline"""
#     # Setup test data
#     test_video_data = json.dumps(
#         {"i": "other_client", "s": mock_client.session_id, "v": "test_frame_data"}
#     ).encode()
#
#     test_audio_data = json.dumps(
#         {
#             "i": "other_client",
#             "s": mock_client.session_id,
#             "a": base64.b64encode(b"test_audio").decode(),
#         }
#     ).encode()
#
#     # Mock socket receive
#     with patch.object(
#         mock_client.sock, "recv", side_effect=[test_video_data, test_audio_data]
#     ):
#         mock_client._recv_data()
#
#         # Verify video frame was stored
#         assert "other_client" in mock_client.faces
#         assert mock_client.faces["other_client"] == "test_frame_data"
#
#         # Verify audio was played (mock checks)
#         assert mock_client.play_stream.write.called
#
#
# def test_render_faces(mock_client: Client) -> None:
#     """Test the face rendering functionality"""
#     # Setup test faces
#     mock_client.faces = {
#         "client1": "line1\nline2\nline3",
#         "client2": "row1\nrow2\nrow3",
#     }
#
#     # Mock system clear and print
#     with patch("os.system"), patch("builtins.print") as mock_print:
#         mock_client._render_faces()
#
#         # Verify output structure
#         assert mock_print.call_count > 0
#         output = "\n".join([call[0][0] for call in mock_print.call_args_list])
#         assert "client1" in output
#         assert "client2" in output
#         assert "line1" in output or "row1" in output
