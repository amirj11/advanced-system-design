from pymongo import MongoClient
import pika
import json
from datetime import datetime
import logging
import os
import sys

EXCHANGE_NAME = "processed_data"  # the save will listen to this exchange
# The saver will listen to these topics in the exchange:
TOPICS_LISTEN = ["user_message", "pose", "color_image", "depth_image", "feelings"]
DB_NAME = "Cortex"
SUPPORTED_QUEUE = ["rabbitmq"]


def init_logger():
    """
    This function initializes the Clients' logger. Logs will be save in Cortex/client/Logs directory.
    """
    now = datetime.now()
    time_string = now.strftime("%d.%m.%Y-%H:%M:%S")
    dir_path = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__), "Logs"))
    if not os.path.exists(dir_path):
        try:
            os.makedirs(dir_path)
        except Exception as e:
            print("Error: could not make Logs directory: {}".format(e))
            sys.exit(1)
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                        filename='{}/saver_{}.log'.format(dir_path, time_string), level=logging.DEBUG,
                        datefmt="%d.%m.%Y-%H:%M:%S")
    logging.getLogger("pika").setLevel(logging.WARNING)


class Saver:

    def __init__(self, database_url):
        init_logger()
        try:
            self.client = MongoClient(database_url)
            self.db = self.client[DB_NAME]
        except Exception as e:
            exit_run("Error connecting to MongoDB: {}".format(e))

    def save(self, topic, data):
        """
        This function connects to the collection "topic" in self.db,
        checks if the message already exists, and if not - registers it in the topic.
        if the message is a parser result, the function will also reister the general snapshots in the "snapshots"
        collection.
        """
        if not data:
            return None
        try:
            collection = self.db[topic]
            try:
                message_content = json.loads(data)
            except ValueError as e:
                logging.error("Received wrong data: {}".format(e))
                return None
            logging.debug("Received data to save: topic {}, user {}".format(topic, message_content["user_id"]))
            # if a user message was received
            if topic == "user_message":
                search = {"user_id": message_content["user_id"]}
                result = collection.find(search).count()
                if result:
                    logging.debug("User {} already Exists in DB. Ignoring".format(message_content["user_id"]))
                    return None

            # if a snapshot message was received
            else:
                search = {"user_id": message_content["user_id"], "datetime": message_content["datetime"]}
                result = collection.find(search).count()
                if result:
                    logging.debug("Already has a record for user {}, topic {}, datetime {}. Ignoring"
                                  .format(message_content["user_id"], topic, message_content["datetime"]))
                    return None

            # if a snapshot message was received, document the snapshot as well
            if topic != "user_message":

                snapshots_collection = self.db["snapshots"]
                time_string = datetime.fromtimestamp(int(str(message_content["datetime"])[:-3])).\
                    strftime("%d.%m.%Y %H:%M:%S")
                time_string = "{}.{}".format(time_string, str(message_content["datetime"])[-3:])
                data = {
                    "user_id": message_content["user_id"],
                    "datetime": message_content["datetime"],
                    "time_string": time_string
                }

                result = snapshots_collection.find(data).count()
                if result == 0:
                    snapshots_collection.insert_one(data)

            # insert the new data (user/parser results) to the DB
            insert = collection.insert_one(message_content)
        except KeyError as e:
            exit_run("KeyError: {}".format(e))

        except Exception as e:
            exit_run("Error connecting to MongoDB: {}".format(e))


def run_saver_wrapper(database_url, mq_url):
    """
    Connects to the message queue, registers to the exchange, and registers to all topics in TOPICS_LISTEN
    Then, consumes messages from the exchange with the listed topics.
    All MQ Code is in this function. This makes it easier to add additional MQ Types in the future.
    """
    try:
        # Check MQ Type and extract host, port
        mq_type, address = mq_url.split('://')
        mq_host, mq_port = address.split(':')
        mq_port = int(str(mq_port).rstrip('/'))
        if mq_type not in SUPPORTED_QUEUE:
            print("MQ Type not supported. please use: {}".format(SUPPORTED_QUEUE))
            exit_run("MQ Not supported: {}".format(mq_type))

        connection = pika.BlockingConnection(pika.ConnectionParameters(mq_host, mq_port))
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic')
        result = channel.queue_declare('', exclusive=True)
        queue_name = result.method.queue

        # register to all the relevant topics in the exchange
        for topic in TOPICS_LISTEN:
            channel.queue_bind(exchange=EXCHANGE_NAME, queue=queue_name, routing_key=topic)

        def callback(ch, method, properties, body):
            saver = Saver(database_url)
            return saver.save(method.routing_key, body)

        channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
        channel.start_consuming()

    except Exception as e:
        exit_run("Error connecting to MQ: {}".format(e))


def exit_run(message):
    logging.error(message)
    print("Error encountered:")
    print(message)
    sys.exit(1)
