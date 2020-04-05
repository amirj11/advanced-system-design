from .cortex_pb2 import *
from datetime import datetime
import os
import json
import logging
import numpy as np
import pika
import pika.exceptions
from PIL import Image
import pathlib
import matplotlib.pyplot as plt

PARSERS = {}
CHANNEL_NAME = "snapshot_message"
EXCHANGE_NAME = "snapshot"
EXCHANGE_PUBLISH = "processed_data"
SUPPORTED_QUEUE = ["rabbitmq"]
PROCESSED_DIRECTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files", "processed")


def init_logger(parser_name):
    """
    This function initializes the Clients' logger. Logs will be save in Cortex/client/Logs directory.
    """
    now = datetime.now()
    time_string = now.strftime("%d.%m.%Y-%H:%M:%S")
    dir_path = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__), "Logs"))
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                        filename='{}/{}_{}.log'.format(dir_path, parser_name, time_string), level=logging.DEBUG,
                        datefmt="%d.%m.%Y-%H:%M:%S")
    logging.getLogger("pika").setLevel(logging.WARNING)


def run_parser_wrapper(parser_name, data=None, mq=None, action="once"):
    """
    will run a parser one time or as a service according to specified type.
    data will be used if running once.
    mq will be the MQ address if running as service.
    """
    parser_name = parser_name.replace('-', '_')

    if parser_name not in globals()["PARSERS"]:
        error_list_parsers()
        sys.exit(1)
    init_logger(parser_name)
    if action == "once":
        try:
            with open(data, "rb") as f:
                data_ = f.read()
        except Exception as e:
            exit_run("Raw data file error: {}".format(e))
        return run_parser(parser_name, data_)
    elif action == "service":
        # Check MQ Type and extract host, port
        try:
            mq_type, address = mq.split('://')
            mq_host, mq_port = address.split(':')
            mq_port = int(str(mq_port).rstrip('/'))
            if mq_type not in SUPPORTED_QUEUE:
                print("MQ Type not supported. please use: {}".format(SUPPORTED_QUEUE))
                exit_run("MQ Not supported: {}".format(mq_type))

        except Exception as e:
            exit_run("Unsupported MQ URL. \n Please use one of the following MQ Types: {} \n MQ URL: type://host:port"
                     .format(SUPPORTED_QUEUE))

        run_parser_service(parser_name, mq_host, mq_port)


def run_parser_service(parser_name, mq_host, mq_port):
    """
    This function is called by __main__ whenever the user wants to start a parser indefinitely,
    without specific data to consume. the process connects to the MQ and starts consuming
    from the queue with the correct parser name. whenever a new message is consumed,
    it is passed to run_parser with the data.
    All MQ Code is in this function. This makes it easier to add additional MQ Types in the future.
    """
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(mq_host, mq_port))
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='direct')
        channel.queue_declare(queue=parser_name)
        channel.queue_bind(exchange=EXCHANGE_NAME, queue=parser_name, routing_key=EXCHANGE_NAME)

        def parser_callback(ch, method, properties, body):
            """
            This function is called by rabbitMQ whenever there is a message to consume.
            the data is forwarded to the appropriate parser which returns the results,
            and then the result is published to the MQ, exchange name EXCHANGE_PUBLISH,
            and the topic name is the parser name.
            """
            result = run_parser(parser_name, body)
            if result is None:
                return
            result_dict = json.loads(result)
            publish_channel = connection.channel()
            publish_channel.exchange_declare(exchange=EXCHANGE_PUBLISH, exchange_type='topic')
            routing_key = parser_name
            logging.debug("Publishing Back to MQ Data processed by {}, user {}, Snapshot {}"
                          .format(parser_name, result_dict["user_id"], result_dict["datetime"]))
            publish_channel.basic_publish(exchange=EXCHANGE_PUBLISH, routing_key=routing_key, body=result)

        channel.basic_consume(queue=parser_name, on_message_callback=parser_callback, auto_ack=True)
        print("{}: Starting to consume".format(parser_name))
        channel.start_consuming()
    except (pika.exceptions.ConnectionClosed, pika.exceptions.AMQPChannelError, pika.exceptions.AMQPError,
            pika.exceptions.NoFreeChannels, pika.exceptions.ConnectionWrongStateError,
            pika.exceptions.ConnectionClosedByBroker) as e:
        exit_run("Error in run_parser_service: {}".format(e))


def run_parser(parser_name, data):
    """
    runs a parser one time on given data.
    used by __main___ whenever a user wants to run a parser on data,
    or by run_parser_service whenever a new message is consumed from some queue.
    """
    parsers = globals()["PARSERS"]
    return parsers[parser_name](data)


def error_list_parsers():
    print("Error: Unknown parser. Available parsers:")
    count = 0
    for parser_type in globals()["PARSERS"]:
        print("{}. {}".format(count + 1, parser_type.replace('_', '-')))
        count += 1

def parser(func):
    """
    a decorator which registers a parser in the global dict PARSERS,
    mapping the name of the parser to the parser function.
    """
    parsers_dict = globals()["PARSERS"]
    parsers_dict[func.__name__] = func
    return func


@parser
def pose(data):
    """
    pose parser. receives JSON string from the MQ, extracts the pose parameters and returns a JSON String.
    """
    snapshot_json = json.loads(data)
    logging.debug("Received Snapshot from user {}, Snapshot {}"
                  .format(snapshot_json["user_id"], snapshot_json["datetime"]))
    try:
        pathlib.Path(PROCESSED_DIRECTORY).mkdir(parents=True, exist_ok=True)

        #  Translation Parsing
        translation_path = "{}/{}_{}_translation.jpg".format(PROCESSED_DIRECTORY, snapshot_json["user_id"],
                                                             snapshot_json["datetime"])

        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        x = snapshot_json["pose_translation_x"]
        y = snapshot_json["pose_translation_y"]
        z = snapshot_json["pose_translation_z"]

        ax.scatter(x, y, z)
        ax.set_xlim3d(-3, 3)
        ax.set_ylim3d(-3, 3)
        ax.set_zlim3d(-3, 3)
        ax.set_xlabel('X Label')
        ax.set_ylabel('Y Label')
        ax.set_zlabel('Z Label')

        x_r = round(x, 3)
        y_r = round(y, 3)
        z_r = round(z, 3)
        ax.text2D(0.05, 0.95, "x: {}, y: {}, z:{}".format(x_r, y_r, z_r), transform=ax.transAxes)

        plt.savefig(translation_path)
        plt.close(fig)

        #  Rotation Parsing
        # fig = plt.figure()
        # ax = fig.add_subplot(111, projection='3d')
        #
        # ax.set_xlim3d(-2, 2)
        # ax.set_ylim3d(-2, 2)
        # ax.set_zlim3d(-2, 2)

        result = {
            "user_id": snapshot_json["user_id"],
            "datetime": snapshot_json["datetime"],
            "rotation_x": snapshot_json["pose_rotation_x"],
            "rotation_y": snapshot_json["pose_rotation_y"],
            "rotation_z": snapshot_json["pose_rotation_z"],
            "rotation_w": snapshot_json["pose_rotation_w"],
            "translation_x": snapshot_json["pose_translation_x"],
            "translation_y": snapshot_json["pose_translation_y"],
            "translation_z": snapshot_json["pose_translation_z"],
            "translation_path": translation_path,
        }

        return json.dumps(result)
    except KeyError as e:
        logging.error("Snapshot {} from user {} did not contain necessary pose data: {}"
                      .format(snapshot_json["datetime"], snapshot_json["user_id"], e))
        return None


@parser
def color_image(data):
    """
    color image parser. receives JSON string from the MQ,
    saves the raw binary color image data as an actual image,
    and publishes its new location and size as a JSON string.
    """
    snapshot_json = json.loads(data)
    logging.debug("Received Snapshot from user {}, Snapshot {}"
                  .format(snapshot_json["user_id"], snapshot_json["datetime"]))

    try:
        with open(snapshot_json["color_image_path"], "rb") as f:
            image_bytes = f.read()
        pathlib.Path(PROCESSED_DIRECTORY).mkdir(parents=True, exist_ok=True)
        final_path = "{}/{}_{}_color.jpg".format(PROCESSED_DIRECTORY, snapshot_json["user_id"],
                                                 snapshot_json["datetime"])
        img = Image.frombytes("RGB", (snapshot_json["color_image_width"], snapshot_json["color_image_height"]),
                              image_bytes)
        img.save(final_path)
        result = {
            "user_id": snapshot_json["user_id"],
            "datetime": snapshot_json["datetime"],
            "color_image_path": final_path,
            "height": snapshot_json["color_image_height"],
            "width": snapshot_json["color_image_width"],
        }
        return json.dumps(result)

    except KeyError as e:
        logging.error("Error: Snapshot {} from user {} did not contain necessary color image data: {}"
                      .format(snapshot_json["datetime"], snapshot_json["user_id"], e))
        return None

    except (OSError, IOError) as e:
        logging.error("Error: file error: {}".format(e))
        return None


@parser
def depth_image(data):
    """
    depth image parser. receives JSON string from the MQ,
    saves the raw binary depth image data as an actual image,
    and publishes its new location and size as a JSON string.
    """
    snapshot_json = json.loads(data)
    logging.debug("Received Snapshot from user {}, Snapshot {}"
                  .format(snapshot_json["user_id"], snapshot_json["datetime"]))
    try:
        with open(snapshot_json["depth_image_path"], "r") as f:
            serialized = f.read()
            data_json = json.loads(serialized)
            image_array = data_json["data"]

        final_path = "{}/{}_{}_depth.jpg".format(PROCESSED_DIRECTORY, snapshot_json["user_id"],
                                                 snapshot_json["datetime"])

        width = snapshot_json["depth_image_width"]
        height = snapshot_json["depth_image_height"]

        new_array = np.reshape(image_array, (height, width))

        pathlib.Path(PROCESSED_DIRECTORY).mkdir(parents=True, exist_ok=True)
        plt.imshow(new_array, cmap='hot', interpolation='nearest')
        plt.savefig(final_path)

        result = {
            "user_id": snapshot_json["user_id"],
            "datetime": snapshot_json["datetime"],
            "height": snapshot_json["depth_image_height"],
            "width": snapshot_json["depth_image_width"],
            "depth_image_path": final_path,
        }
        return json.dumps(result)
    except KeyError as e:
        logging.error("Snapshot {} from user {} did not have necessary depth image data: {}"
                      .format(snapshot_json["datetime"], snapshot_json["user_id"], e))
        return None

    except (OSError, IOError) as e:
        logging.error("Error: file error for snapshot {} by user {}: {}"
                      .format(snapshot_json["datetime"], snapshot_json["user_id"], e))
        None


@parser
def feelings(data):
    """
    feelings parser. receives JSON string data from the MQ, publishes back the feelings as JSON string.
    """
    snapshot_json = json.loads(data)
    logging.debug("Received Snapshot from user {}, Snapshot {}"
                  .format(snapshot_json["user_id"], snapshot_json["datetime"]))
    try:
        result = {
            "user_id": snapshot_json["user_id"],
            "datetime": snapshot_json["datetime"],
            "happiness": snapshot_json["happiness"],
            "thirst": snapshot_json["thirst"],
            "hunger": snapshot_json["hunger"],
            "exhaustion": snapshot_json["exhaustion"],
        }
        return json.dumps(result)
    except KeyError as e:
        logging.error("Snapshot {} by user {} did not contain all necessary feelings data: {}"
                      .format(snapshot_json["datetime"], snapshot_json["user_id"], e))
        return None


def exit_run(message):
    logging.error(message)
    print("Error encountered:")
    print(message)
    sys.exit(1)
