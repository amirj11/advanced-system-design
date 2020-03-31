from click.exceptions import UsageError
from ..client import client
from .cortex_pb2 import *
import pytest
import subprocess

HOST = "127.0.0.1"
PORT = 8000
SAMPLE_FILE = "../client/sample.mind.gz"


def test_cli_error_1():

    process = subprocess.Popen(
        ['python', "-m", "cortex.client", "upload", "-h", HOST, "-p", str(PORT), SAMPLE_FILE],
        stdout=subprocess.PIPE,
    )
    stdout, _ = process.communicate()
    assert b'Error' in stdout


def test_cli_error_2():

    process = subprocess.Popen(
        ['python', "-m", "cortex.client", "-h", HOST, "-p", str(PORT), SAMPLE_FILE],
        stdout=subprocess.PIPE,
    )
    stdout, _ = process.communicate()
    assert b'Error' in stdout

def test_cli_error_3():

    process = subprocess.Popen(
        ['python', "-m", "cortex.client", "upload-sample", "-p", str(PORT), SAMPLE_FILE],
        stdout=subprocess.PIPE,
    )
    stdout, _ = process.communicate()
    assert b'Error' in stdout


def test_cli_error_4():

    process = subprocess.Popen(
        ['python', "-m", "cortex.client", "upload", "-h", HOST, SAMPLE_FILE],
        stdout=subprocess.PIPE,
    )
    stdout, _ = process.communicate()
    assert b'Error' in stdout


def test_cli_error_5():

    process = subprocess.Popen(
        ['python', "-m", "cortex.client", "upload-sample", SAMPLE_FILE],
        stdout=subprocess.PIPE,
    )
    stdout, _ = process.communicate()
    assert b'Error' in stdout


def test_re_serialize_user():

    user_message = User()
    user_message.username = "Test User"
    user_message.user_id = 1
    user_message.gender = 0
    user_message.birthday = 100

    re_serialized = client.reserialize_user(user_message.SerializeToString())
    new_message = User()
    new_message.ParseFromString(re_serialized)

    assert new_message.username == "Test User"
    assert new_message.user_id == 1
    assert new_message.gender == 0
    assert new_message.birthday == 100


def test_re_serialize_snapshot():

    snapshot = Snapshot()
    snapshot.datetime = 12345

    snapshot.pose.translation.x = 0.005
    snapshot.pose.rotation.x = 0.96
    snapshot.color_image.width = 5
    snapshot.depth_image.height = 10
    snapshot.feelings.thirst = 0.5

    re_serialized = client.reserialize_snapshot(snapshot.SerializeToString())
    new_snapshot = Snapshot()
    new_snapshot.ParseFromString(re_serialized)

    assert new_snapshot.datetime == 12345
    assert new_snapshot.pose.translation.x == 0.005
    assert new_snapshot.pose.rotation.x == 0.96
    assert new_snapshot.color_image.width == 5
    assert new_snapshot.depth_image.height == 10
    assert new_snapshot.feelings.thirst == 0.5


def test_upload_sample_1():
    """
    Trying to upload an unknown file protocol.
    """
    with pytest.raises(SystemExit):
        client.upload_sample(None, None, None, "Unknown_Protocol")


def test_upload_sample_host_1():
    with pytest.raises(SystemExit):
        client.upload_sample(None, 5000, SAMPLE_FILE)


def test_upload_sample_host_2():
    with pytest.raises(SystemExit):
        client.upload_sample("1.2.3.4", 5000, SAMPLE_FILE)


def test_upload_sample_host_3():
    with pytest.raises(SystemExit):
        client.upload_sample("somehost", 5000, SAMPLE_FILE)


def test_upload_sample_port_1():
    with pytest.raises(SystemExit):
        client.upload_sample("127.0.0.1", None, SAMPLE_FILE)


def test_upload_sample_port_2():
    with pytest.raises(SystemExit):
        client.upload_sample("127.0.0.1", -1, SAMPLE_FILE)


def test_upload_sample_port_3():
    with pytest.raises(SystemExit):
        client.upload_sample("127.0.0.1", "port", SAMPLE_FILE)


def test_upload_sample_host_port():
    with pytest.raises(SystemExit):
        client.upload_sample(None, None, SAMPLE_FILE)


def test_upload_sample_file_1():
    with pytest.raises(SystemExit):
        client.upload_sample("127.0.0.1", 5000, "unreal.file")

