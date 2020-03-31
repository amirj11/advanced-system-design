import json
import subprocess
from ..saver import saver
import pytest

MQ_URL = "mongodb://127.0.0.1:27017/"
DB_URL = "localhost"

data = {
    "test1": "test2"
}
data_json = json.dumps(data)


def test_connection_failed():
    mq_wrong_url = "mongodb://127.0.0.1:80"

    with pytest.raises(SystemExit):
        saver_ = saver.Saver(mq_wrong_url)
        saver_.save("pose", data_json)


def test_none_data():
    """
    data is None
    """
    saver_ = saver.Saver(MQ_URL)
    result = saver_.save("pose", None)
    assert result is None


def test_wrong_data_2():
    """
    non json data.
    """
    saver_ = saver.Saver(MQ_URL)
    result = saver_.save("topic", "data")
    assert result is None



def test_cli_error_1():
    """
    non existing action.
    """
    process = subprocess.Popen(
        ['python', "-m", "cortex.saver", "wrong_action", "-d", MQ_URL, "pose", data_json],
        stdout=subprocess.PIPE,
    )
    stdout, _ = process.communicate()
    assert b'Error' in stdout


def test_cli_error_2():
    """
    non-existing parser.
    """
    process = subprocess.Popen(
        ['python', "-m", "cortex.saver", "save", "-d", MQ_URL, "wrong_parser", data_json],
        stdout=subprocess.PIPE,
    )
    stdout, _ = process.communicate()
    assert b'Error' in stdout


def test_cli_error_3():
    """
    no data.
    """
    process = subprocess.Popen(
        ['python', "-m", "cortex.saver", "save", "-d", MQ_URL, "pose"],
        stdout=subprocess.PIPE,
    )
    stdout, _ = process.communicate()
    assert b'Error' in stdout


def test_cli_error_4():
    """
    no MQ URL.
    """
    process = subprocess.Popen(
        ['python', "-m", "cortex.saver", "run-saver", DB_URL],
        stdout=subprocess.PIPE,
    )
    stdout, _ = process.communicate()
    assert b'Error' in stdout