from ..server import server
from .cortex_pb2 import *
import pytest
import json
import subprocess

HOST = "127.0.0.1"
PORT = 8000
MQ_URL = "rabbitmq://127.0.0.1:5672"


def test_cli_error_1():

    process = subprocess.Popen(
        ['python', "-m", "cortex.server", "run", "-h", HOST, "-p", str(PORT), MQ_URL],
        stdout=subprocess.PIPE,
    )
    stdout, _ = process.communicate()
    assert b'Error' in stdout


def test_cli_error_2():

    process = subprocess.Popen(
        ['python', "-m", "cortex.server", "-h", HOST, "-p", str(PORT), MQ_URL],
        stdout=subprocess.PIPE,
    )
    stdout, _ = process.communicate()
    assert b'Error' in stdout


# def test_cli_error_3():
#
#     process = subprocess.Popen(
#         ['python', "-m", "cortex.server", "run-server"],
#         stdout=subprocess.PIPE,
#     )
#     stdout, _ = process.communicate()
#     assert b'Error' in stdout


def test_user_json():

    user_message = User()
    user_message.username = "Test User"
    user_message.user_id = 1
    user_message.gender = 0
    user_message.birthday = 100

    re_serialized = server.user_to_json(user_message.SerializeToString())
    new_message = json.loads(re_serialized)

    assert new_message["username"] == "Test User"
    assert new_message["user_id"] == 1
    assert new_message["gender"] == 0
    assert new_message["birthday"] == 100


def test_snapshot_json():

    snapshot = Snapshot()
    snapshot.datetime = 12345

    snapshot.pose.translation.x = 0.005
    snapshot.pose.rotation.x = 0.96
    snapshot.color_image.width = 5
    snapshot.depth_image.height = 10
    snapshot.feelings.thirst = 0.5

    re_serialized = server.snapshot_to_json(snapshot.SerializeToString(), 1)
    new_snapshot = json.loads(re_serialized)

    assert new_snapshot["user_id"] == 1
    assert new_snapshot["datetime"] == 12345
    assert new_snapshot["pose_translation_x"] == 0.005
    assert new_snapshot["pose_rotation_x"] == 0.96
    assert new_snapshot["color_image_width"] == 5
    assert new_snapshot["depth_image_height"] == 10
    assert new_snapshot["thirst"] == 0.5


def test_run_server_1():
    """
    None parameters.
    """
    with pytest.raises(SystemExit):
        server.run_server(None, None, None)


def test_run_server_2():
    """
    Illegal port.
    """
    with pytest.raises(SystemExit):
        server.run_server(HOST, -1, MQ_URL, publish_method="message_queue")


def test_run_server_3():
    """
    illegal host.
    """
    with pytest.raises(SystemExit):
        server.run_server("1.2.3.4", 8000, MQ_URL, publish_method="message_queue")


def test_run_server_4():
    """
    illegal publishing method.
    """
    with pytest.raises(SystemExit):
        server.run_server("127.0.0.1", 8000, MQ_URL, publish_method="test")
