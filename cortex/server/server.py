from flask import Flask
from flask_restful import Resource, Api, request
from .cortex_pb2 import *
from datetime import datetime
import json
import logging
import os
import pika
import pika.exceptions
import pathlib


app = Flask(__name__)
api = Api(app)

SUPPORTED_QUEUE = ["rabbitmq"]
PUBLISH_METHOD = None  # will be set to "message_queue" or "function"
PUBLISH = None  # will contain the function / message queue address
MQ_PORT = None
MQ_TYPE = None
EXCHANGE_NAME = "snapshot"  # will publish snapshots to this exchange
USER_MESSAGE_EXCHANGE = "processed_data"  # will publish user meesages to this exchange
USER_MESSAGE_TOPIC = "user_message"  # will publish user messages to this topic
RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files", "raw")
PUBLISH_METHODS = ["function", "message_queue"]  # available publishing methods the data


def init_logger():
	"""
	This function initializes the servers' logger. Logs will be save in Cortex/server/Logs directory.
	"""
	now = datetime.now()
	time_string = now.strftime("%d.%m.%Y-%H:%M:%S")
	dir_path = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__), "Logs"))
	if not os.path.exists(dir_path):
		try:
			os.makedirs(dir_path)
		except OSError as e:
			print("Fatal Error: could not create 'Logs' directory: {}".format(e))
			sys.exit(1)
	logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
						filename='{}/server_{}.log'.format(dir_path, time_string), level=logging.DEBUG,
						datefmt="%d.%m.%Y-%H:%M:%S")
	logging.getLogger("werkzeug").setLevel(logging.WARNING)
	logging.getLogger("pika").setLevel(logging.WARNING)


class GetSnapshotMessage(Resource):
	"""
	This class handles REST API for snapshots messages sent to the server.
	each snapshot is sent to url /api/snapshot_message/<user_id>
	the class saves the raw data of the color image and depth image in files inside RAW_DIR.
	it then deserializes and reserializes the snapshot as JSON, and publishes to MQ/function.
	"""
	def post(self, user_id):
		logging.debug("Got Snapshot for user {}".format(user_id))

		# get snapshot from POST data and deserialize it
		request.get_data()
		data = request.data
		snapshot_message = Snapshot()
		snapshot_message.ParseFromString(data)

		# re-serializing the snapshot into JSON, to de-couple the client-server protocol
		# from the server-mq protocol.
		pathlib.Path("{}".format(RAW_DIR)).mkdir(parents=True, exist_ok=True)
		# save color image data as binary
		color_image_path = "{}/{}_{}_color".format(RAW_DIR, user_id, snapshot_message.datetime)
		try:
			with open(color_image_path, "wb") as f:
				f.write(snapshot_message.color_image.data)
		except EnvironmentError as e:
			logging.error("Could not open {}: {}".format(color_image_path, e))
			sys.exit(1)
		# save depth image data as json string
		depth_image_path = "{}/{}_{}_depth".format(RAW_DIR, user_id, snapshot_message.datetime)
		try:
			with open(depth_image_path, "w") as f:
				new_array = []
				for item in snapshot_message.depth_image.data:
					new_array.append(item)
				result = {
					"data": new_array,
				}
				serialized = json.dumps(result)
				f.write(serialized)
		except EnvironmentError as e:
			exit_run("Could not open {}: {}".format(depth_image_path, e))

		snapshot_json = snapshot_to_json(data, user_id)
		if globals()["PUBLISH_METHOD"] == "message_queue":
			logging.debug("Publishing Snapshot {} for user {} to MQ".format(snapshot_message.datetime, user_id))
			publish_snapshot(snapshot_json)

		elif globals()["PUBLISH_METHOD"] == "function":
			logging.debug("Passing Snapshot {} for user {} to function.".format(snapshot_message.datetime, user_id))
			globals()["PUBLISH"](snapshot_json)

		return 200


class GetUserMessage(Resource):
	"""
	This class handles REST API for user messages sent to the server.
	each snapshot is sent to url /api/user_message/<user_id>
	it then deserializes and reserializes the message as JSON, and publishes to MQ/function.
	"""
	def post(self, user_id):
		request.get_data()
		logging.debug("Got user message for user {}".format(user_id))
		data = request.data
		user_json = user_to_json(data)
		if globals()["PUBLISH_METHOD"] == "message_queue":
			logging.debug("Publishing user message for user {} to MQ".format(user_id))
			publish_user_message(user_json)

		elif globals()["PUBLISH_METHOD"] == "function":
			logging.debug("Passing user message for user {} to function".format(user_id))
			globals()["PUBLISH"](user_json)

		return 200


api.add_resource(GetUserMessage, '/api/user_message/<user_id>')
api.add_resource(GetSnapshotMessage, '/api/snapshot_message/<user_id>')


def run_server(host, port, publish, publish_method="function"):
	"""
	This functions initializes the server.
	publish - string, containing the MQ Address or function.
	publish_method = string, "function" or "message_queue" - that is where the data will be redirected.
	"""
	if host is None or port is None or publish is None:
		print("None parameters not allowed: host={}, port={}, publish={}".format(host, port, publish))
		sys.exit(1)

	if publish_method not in PUBLISH_METHODS:
		print("Publish method {} is not allowed".format(publish_method))
		sys.exit(1)

	init_logger()
	logging.debug("Initiating Server.")
	global_variables = globals()

	#  if using MQ - verify MQ type and extract host, port
	if publish_method == "message_queue":
		mq_type, address = publish.split('://')
		mq_host, mq_port = address.split(':')
		mq_port = int(str(mq_port).rstrip('/'))
		if mq_type not in SUPPORTED_QUEUE:
			exit_run("MQ Type not supported. please use: {}".format(SUPPORTED_QUEUE))
		global_variables["PUBLISH"] = mq_host
		global_variables["MQ_PORT"] = mq_port

	elif publish_method == "function":
		global_variables["PUBLISH"] = publish

	global_variables["PUBLISH_METHOD"] = publish_method
	logging.debug("Publish Method: {}".format(publish_method))
	logging.debug("Publish Destination: {}".format(publish))
	try:
		app.run(host=host, port=port)  # this is blocking!

	except Exception as e:
		exit_run("Error: Could not start server: {}".format(e))


def publish_snapshot(message):
	"""
	publishes a snapshot message to the MQ.
	a message is a serialized JSON message.
	the function uses direct routing to an exchange called EXCHANGE_NAME.
	all snapshot parsers register to this exchange and receive a copy of the message.
	The use of a publishing function allows for easy addition of different MQ types in the future.
	"""
	try:
		global_variables = globals()
		connection = pika.BlockingConnection(pika.ConnectionParameters(global_variables["PUBLISH"], global_variables["MQ_PORT"]))
		channel = connection.channel()
		channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='direct')
		channel.basic_publish(exchange=EXCHANGE_NAME, routing_key=EXCHANGE_NAME, body=message)
		connection.close()

	except (pika.exceptions.ConnectionClosed, pika.exceptions.AMQPChannelError, pika.exceptions.AMQPError,
			pika.exceptions.NoFreeChannels, pika.exceptions.ConnectionWrongStateError) as e:
		exit_run("Error publishing snapshot to MQ: {}".format(e))


def publish_user_message(message):
	"""
	publishes a user message to the MQ.
	a message if a serialized JSON message.
	the user message will not be arriving to a parser, but will be directly read by the saver.
	the function publishes to an exchange called USER_MESSAGE_EXCHANGE
	with USER_MESSAGE_TOPIC as routing key, which the saver listens to.
	exchange USER_MESSAGE_EXCHANGE is identical to the exchange used by parsers to publish finished data,
	so the saver receives the user message just like a finished processed message from parsers.
	The use of a publishing function allows for easy addition of different MQ types in the future.
	"""
	try:
		global_variables = globals()
		connection = pika.BlockingConnection(pika.ConnectionParameters(global_variables["PUBLISH"], global_variables["MQ_PORT"]))
		publish_channel = connection.channel()
		publish_channel.exchange_declare(exchange=USER_MESSAGE_EXCHANGE, exchange_type='topic')
		routing_key = USER_MESSAGE_TOPIC
		publish_channel.basic_publish(exchange=USER_MESSAGE_EXCHANGE, routing_key=routing_key, body=message)

	except (pika.exceptions.ConnectionClosed, pika.exceptions.AMQPChannelError, pika.exceptions.AMQPError,
			pika.exceptions.NoFreeChannels, pika.exceptions.ConnectionWrongStateError,
			pika.exceptions.ConnectionClosedByBroker) as e:
		exit_run("Error publishing user message to MQ: {}".format(e))


def user_to_json(data):
	"""
	receives raw serialized data of a user message sent from the client, and changes it to JSON.
	returns a JSON string.
	"""
	user_message = User()
	user_message.ParseFromString(data)
	result = {
		"user_id": user_message.user_id,
		"username": user_message.username,
		"birthday": user_message.birthday,
		"gender": user_message.gender,
	}
	return json.dumps(result)


def snapshot_to_json(data, user_id):
	"""
	receives raw serialized data of a snapshot message sent from the client, and chanegs it to JSON.
	incorporates the user id into the JSON, alongside the paths for the color and depth image.
	returns a JSON string.
	"""
	snapshot = Snapshot()
	snapshot.ParseFromString(data)
	color_path = "{}/{}_{}_color".format(RAW_DIR, user_id, snapshot.datetime)
	depth_path = "{}/{}_{}_depth".format(RAW_DIR, user_id, snapshot.datetime)
	result = {
		"user_id": user_id,
		"datetime": snapshot.datetime,
		"color_image_path": color_path,
		"depth_image_path": depth_path,
		"pose_rotation_x": snapshot.pose.rotation.x,
		"pose_rotation_y": snapshot.pose.rotation.y,
		"pose_rotation_z": snapshot.pose.rotation.z,
		"pose_rotation_w": snapshot.pose.rotation.w,
		"pose_translation_x": snapshot.pose.translation.x,
		"pose_translation_y": snapshot.pose.translation.y,
		"pose_translation_z": snapshot.pose.translation.z,
		"color_image_height": snapshot.color_image.height,
		"color_image_width": snapshot.color_image.width,
		"depth_image_height": snapshot.depth_image.height,
		"depth_image_width": snapshot.depth_image.width,
		"hunger": snapshot.feelings.hunger,
		"thirst": snapshot.feelings.thirst,
		"exhaustion": snapshot.feelings.exhaustion,
		"happiness": snapshot.feelings.happiness,
	}
	return json.dumps(result)


def exit_run(message):
	logging.error(message)
	print("Error encountered:")
	print(message)
	sys.exit(1)
