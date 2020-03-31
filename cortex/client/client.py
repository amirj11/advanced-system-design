from .cortex_pb2 import *
from datetime import datetime
import gzip
import logging
import os
import requests
import struct
import sys


def init_logger():
    """
    This function initializes the Clients' logger. Logs will be save in Cortex/client/Logs directory.
    """
    now = datetime.now()
    time_string = now.strftime("%d.%m.%Y-%H:%M:%S")
    dir_path = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__), "Logs"))
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    print(dir_path)
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                        filename='{}/client_{}.log'.format(dir_path, time_string), level=logging.DEBUG,
                        datefmt="%d.%m.%Y-%H:%M:%S")
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


PROTOCOLS = ["ProtoBuf"]
USER_MESSAGE_API = "api/user_message"
SNAPSHOT_MESSAGE_API = "api/snapshot_message"


def upload_sample(host, port, path, protocol="ProtoBuf"):
    """
    This function gets server details (host, port),
    a path to sample file, and a protocol.
    the function deserializes the data according to the procotol, re-serializes it to the Cortex ProtoBuf format,
    and sends it to the server. it operated on a single message each time, never reading more than one message
    or snapshot from the file into the memory.
    it sends the user message first and then loops over all snapshots.
    """
    init_logger()
    if host is None or port is None or path is None:
        logging.error("Parameters can't be None: host={}, port={}, path={}".format(host, port, path))
        sys.exit(1)
    if protocol not in PROTOCOLS:
        logging.error("Attempted use of unknown protocol: {}".format(protocol))
        exit_run()

    if protocol == "ProtoBuf":
        sample_file = ""
        try:
            sample_file = gzip.open(path, 'rb')
        except FileNotFoundError:
            logging.error("Sample file not found: {}".format(path))
            exit_run()

        # deserialize user data from sample file, and reserialize it into a new ProtoBuf User() message
        user_message_size = struct.unpack('I', sample_file.read(4))[0]

        raw_message = sample_file.read(user_message_size)
        new_serialized_message = reserialize_user(raw_message, protocol)
        new_user_message = User()
        new_user_message.ParseFromString(new_serialized_message)

        # send user message data to server
        user_message_url = "http://{}:{}/{}/{}".format(host, port, USER_MESSAGE_API, new_user_message.user_id)
        headers = {'Content-Type': 'application/octet-stream'}
        try:
            send = requests.post(user_message_url, data=new_serialized_message, headers=headers, timeout=1.5)
            logging.debug("Sent user message ({}, {}): return code {}".format(new_user_message.username,
                                                                              new_user_message.user_id,
                                                                              send.status_code))
        except Exception as e:
            logging.error("Could not send user message to server: {}".format(e))
            exit_run()

        count = 1
        while len(snapshot_size_bin := sample_file.read(4)) > 0:

            # read snapshot, re-serialize it to the ProtoBuf, and send it to the server
            snapshot_size = struct.unpack('I', snapshot_size_bin)[0]
            raw_message = sample_file.read(snapshot_size)
            new_serialized_snapshot = reserialize_snapshot(raw_message, protocol)
            new_snapshot = Snapshot()
            new_snapshot.ParseFromString(new_serialized_snapshot)
            snapshot_message_url = "http://{}:{}/{}/{}".format(host, port, SNAPSHOT_MESSAGE_API,
                                                               new_user_message.user_id)
            headers = {'Content-Type': 'application/octet-stream'}
            try:
                send = requests.post(snapshot_message_url, data=new_serialized_snapshot, headers=headers, timeout=1.5)
                logging.debug("Sent user {} ({}) Snapshot #{}: return code {}".format(new_user_message.username,
                                                                                      new_user_message.user_id,
                                                                                      new_snapshot.datetime,
                                                                                      send.status_code))

                print("Snapshot {} uploaded ({}, {})".format(count, new_user_message.username,
                                                             new_user_message.user_id))
            except Exception as e:
                logging.error("Could not send snapshot message to server: {}".format(e))
                exit_run()
            count += 1

        logging.debug("Finished uploading snapshots for user {}. Number of snapshots: {}"
                      .format(new_user_message.user_id, count))


def reserialize_user(raw_message, protocol="ProtoBuf"):
    """
    This function gets a serialized user message and a protocol.
    it deserializes the user message according to the mentioned protocol, spreads it to memory,
    and produces a new serialized user message according to the Cortex ProtoBuf format.
    """
    if protocol == "ProtoBuf":
        old_user_message = User()
        old_user_message.ParseFromString(raw_message)
        new_user_message = User()

        new_user_message.user_id = old_user_message.user_id
        new_user_message.username = old_user_message.username
        new_user_message.birthday = old_user_message.birthday
        new_user_message.gender = old_user_message.gender

        return new_user_message.SerializeToString()


def reserialize_snapshot(raw_message, protocol="ProtoBuf"):
    """
    This function gets a serialized snapshot and a protocol.
    it deserializes the snapshot according to the mentioned protocol, spreads it to memory,
    and produces a new serialized snapshot according to the Cortex ProtoBuf format.
    """

    if protocol == "ProtoBuf":

        old_snapshot = Snapshot()
        old_snapshot.ParseFromString(raw_message)
        snapshot_message = Snapshot()

        snapshot_message.datetime = old_snapshot.datetime

        snapshot_message.pose.translation.x = old_snapshot.pose.translation.x
        snapshot_message.pose.translation.y = old_snapshot.pose.translation.y
        snapshot_message.pose.translation.z = old_snapshot.pose.translation.z

        snapshot_message.pose.rotation.x = old_snapshot.pose.rotation.x
        snapshot_message.pose.rotation.y = old_snapshot.pose.rotation.y
        snapshot_message.pose.rotation.z = old_snapshot.pose.rotation.z
        snapshot_message.pose.rotation.w = old_snapshot.pose.rotation.w

        snapshot_message.color_image.width = old_snapshot.color_image.width
        snapshot_message.color_image.height = old_snapshot.color_image.height
        snapshot_message.color_image.data = old_snapshot.color_image.data

        snapshot_message.depth_image.width = old_snapshot.depth_image.width
        snapshot_message.depth_image.height = old_snapshot.depth_image.height
        snapshot_message.depth_image.data.extend(old_snapshot.depth_image.data)

        snapshot_message.feelings.hunger = old_snapshot.feelings.hunger
        snapshot_message.feelings.thirst = old_snapshot.feelings.thirst
        snapshot_message.feelings.exhaustion = old_snapshot.feelings.exhaustion
        snapshot_message.feelings.happiness = old_snapshot.feelings.happiness

        return snapshot_message.SerializeToString()


def exit_run():
    print("Error encountered. Please see log for details")
    sys.exit(1)