import json
import subprocess
import os
from ..parsers import parsers


PROCESSED_DIRECTORY = "/tmp/Cortex/processed"

#  complete snapshot data
correct_data = {
    "user_id": 50,
    "datetime": 12345,
    "color_image_path": "color",
    "depth_image_path": "depth",
    "pose_rotation_x": 0.1,
    "pose_rotation_y": 0.2,
    "pose_rotation_z": 0.3,
    "pose_rotation_w": 0.4,
    "pose_translation_x": 0.5,
    "pose_translation_y": 0.6,
    "pose_translation_z": 0.7,
    "color_image_height": 1080,
    "color_image_width": 1920,
    "depth_image_height": 172,
    "depth_image_width": 224,
    "hunger": 1,
    "thirst": 2,
    "exhaustion": 3,
    "happiness": 4,
}

correct_data_json = json.dumps(correct_data)

#  incomplete data for each parser: pose, color image, depth image, feelings
missing_data = {
    "user_id": 50,
    "datetime": 12345,
    "color_image_path": "color",
    "depth_image_path": "depth",
    "pose_rotation_x": 0.1,
    "pose_rotation_y": 0.2,
    "pose_rotation_z": 0.3,
    "pose_translation_x": 0.5,
    "pose_translation_y": 0.6,
    "pose_translation_z": 0.7,
    "color_image_height": 1,
    "depth_image_width": 4,
    "hunger": 1,
    "exhaustion": 3,
    "happiness": 4,
}


missing_data_json = json.dumps(missing_data)


def test_pose_1():
    """
    test pose success.
    """
    result = parsers.run_parser("pose", correct_data_json)
    result_dict = json.loads(result)
    assert result_dict["user_id"] == 50
    assert result_dict["datetime"] == 12345
    assert result_dict["rotation_x"] == 0.1
    assert result_dict["rotation_y"] == 0.2
    assert result_dict["rotation_z"] == 0.3
    assert result_dict["rotation_w"] == 0.4
    assert result_dict["translation_x"] == 0.5
    assert result_dict["translation_y"] == 0.6
    assert result_dict["translation_z"] == 0.7


def test_pose_2():
    """
    test pose failure, not all pose data inside snapshot.
    """
    result = parsers.run_parser("pose", missing_data_json)
    assert result is None


def test_color_image_1():
    """
    test color image success.
    """
    result = parsers.run_parser("color_image", correct_data_json)
    result_dict = json.loads(result)
    assert result_dict["user_id"] == 50
    assert result_dict["datetime"] == 12345
    image_path = "{}/{}_{}_color.jpg".format(PROCESSED_DIRECTORY, result_dict["user_id"], result_dict["datetime"])
    assert result_dict["color_image_path"] == image_path
    assert result_dict["height"] == 1080
    assert result_dict["width"] == 1920
    os.remove(image_path)


def test_color_image_2():
    """
    test color image failure. not all color image data inside snapshot.
    """
    result = parsers.run_parser("color_image", missing_data_json)
    assert result is None


def test_color_image_3():
    """
    test color image failure when binary image data can't be found.
    """
    data = correct_data
    data["color_image_path"] = "nonexistent_file"
    data_json = json.dumps(data)
    result = parsers.run_parser("color_image", data_json)
    assert result is None


def test_depth_image_1():
    """
    test depth image success.
    """
    result = parsers.run_parser("depth_image", correct_data_json)
    result_dict = json.loads(result)
    assert result_dict["user_id"] == 50
    assert result_dict["datetime"] == 12345
    image_path = "{}/{}_{}_depth.jpg".format(PROCESSED_DIRECTORY, result_dict["user_id"], result_dict["datetime"])
    assert result_dict["depth_image_path"] == image_path
    assert result_dict["height"] == 172
    assert result_dict["width"] == 224
    os.remove(image_path)


def test_depth_image_2():
    """
    test depth image failure, not all depth image data inside snapshot.
    """
    result = parsers.run_parser("depth_image", missing_data_json)
    assert result is None


def test_depth_image_3():
    """
    test depth image failure, can't find depth image binary data.
    """
    data = correct_data
    data["depth_image_path"] = "nonexistent_file"
    data_json = json.dumps(data)
    result = parsers.run_parser("depth_image", data_json)
    assert result is None


def test_feelings_1():
    """
    test feelings success.
    """
    result = parsers.run_parser("feelings", correct_data_json)
    result_dict = json.loads(result)
    assert result_dict["user_id"] == 50
    assert result_dict["datetime"] == 12345
    assert result_dict["hunger"] == 1
    assert result_dict["thirst"] == 2
    assert result_dict["exhaustion"] == 3
    assert result_dict["happiness"] == 4


def test_feelings_2():
    """
    test feelings failure, not all feelings inside snapshot.
    """
    result = parsers.run_parser("feelings", missing_data_json)
    assert result is None


def test_cli_error_1():
    """
    wrong parser name.
    """
    process = subprocess.Popen(
        ['python', "-m", "cortex.parsers", "parse", "nonexistent_parser", correct_data_json],
        stdout=subprocess.PIPE,
    )
    stdout, _ = process.communicate()
    assert b'Error' in stdout


def test_cli_error_2():
    """
    wrong data.
    """
    process = subprocess.Popen(
        ['python', "-m", "cortex.parsers", "parse", "pose", "nonexistent_data"],
        stdout=subprocess.PIPE,
    )
    stdout, _ = process.communicate()
    assert b'Error' in stdout


def test_cli_error_3():
    """
    wrong action.
    """
    process = subprocess.Popen(
        ['python', "-m", "cortex.parsers", "action", "pose", "nonexistent_data_"],
        stdout=subprocess.PIPE,
    )
    stdout, _ = process.communicate()
    assert b'Error' in stdout


def test_cli_error_4():
    """
    missing required arguments .
    """
    process = subprocess.Popen(
        ['python', "-m", "cortex.parsers", "parse", "pose"],
        stdout=subprocess.PIPE,
    )
    stdout, _ = process.communicate()
    assert b'Error' in stdout
