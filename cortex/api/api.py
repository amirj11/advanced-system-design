from flask import Flask, abort, make_response
from flask_restful import Resource, Api, request
from datetime import datetime
import logging
import os
from pymongo import MongoClient
import sys

app = Flask(__name__)
api_ = Api(app)

DB_NAME = "Cortex"
DB_CONNECTION = None
RESULTS = ["pose", "color_image", "depth_image", "feelings"]

""""
this dictionary contains list of values inside each parser DB table. these values will not be returned to the user
when he uses the CLI.
for example: the value of "color_image_path" will not be returned to the user when he requests
the results of the parser "color_image" of some snapshot.
"""
RESULTS_IGNORE = {"pose": [], "feelings": [], "color_image": ["color_image_path"], "depth_image": ["depth_image_path"]}

"""
This dictionary contains values that will be added to the response for each result-name, but don't appear in the DB.
"""
RESULTS_ADD = {"pose": {}, "feelings": {}, "color_image": {"data": "data"}, "depth_image": {"data": "data"}}

"""
This dictionary contains the DB values of the binary data for results that contain binary data.
key: parser name
value: db value with the binary data
"""
PATHS = {"color_image": "color_image_path", "depth_image": "depth_image_path"}


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
                        filename='{}/api_{}.log'.format(dir_path, time_string), level=logging.DEBUG,
                        datefmt="%d.%m.%Y-%H:%M:%S")
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


class GetUsers(Resource):
    """
    returns a JSON list of the system users to the user.
    """
    def get(self):
        try:
            collection = DB_CONNECTION["user_message"]
            data = []
            for user in collection.find({}, {"_id": 0, "user_id": 1, "username": 1}):
                print(user)
                user = [user["username"], user["user_id"]]
                data.append(user)
            return data
        except Exception as e:
            logging.error("Could not connect to DB: {}".format(e))
            exit_run()


class GetUser(Resource):
    """
    returns the user details to the user.
    """
    def get(self, user_id):

        result = get_user(int(user_id))
        if not result:
            logging.error("User {} does not exist".format(user_id))
            abort(404)

        data = {
            "username": result["username"],
            "user_id": result["user_id"],
            "birthday": result["birthday"],
            "gender": result["gender"]
        }

        return data


class GetUserSnapshots(Resource):
    """
    A snapshot ID is it's datetime.
    if user does not exists, returns 404.
    if user exists but has no snapshots, returns empty list.
    """
    def get(self, user_id):

        if not get_user(int(user_id)):
            logging.error("User {} does not exist".format(user_id))
            abort(404)
        try:
            collection = DB_CONNECTION["snapshots"]
            search = {"user_id": user_id}
            result = collection.find(search)
            data = []
            for snapshot in result:
                print("Snapshot: {}.{}".format(snapshot["_id"], snapshot["datetime"]))
                data.append(snapshot["datetime"])
            return data
        except Exception as e:
            logging.error("Could not connect to DB: {}".format(e))
            exit_run()


class GetSnapshotById(Resource):
    """
    if user does not exists, return 404.
    if user exists but snapshot ID does not, return 404.

    """
    def get(self, user_id, snapshot_id):

        if not get_user(int(user_id)):
            logging.error("User {} does not exist".format(user_id))
            abort(404)

        result = user_snapshot(user_id, snapshot_id)
        if not result:  # snapshot ID does not exist for user
            logging.error("Snapshot {} for User {} does not exist".format(snapshot_id, user_id))
            abort(404)
        try:
            data = [result["datetime"]]
            for parser in RESULTS:
                collection = DB_CONNECTION[parser]
                search = {"user_id": user_id, "datetime": int(snapshot_id)}
                result = collection.find_one(search)
                if result:
                    data.append(parser.replace('_', '-'))
            return data
        except Exception as e:
            logging.error("Could not connect to DB: {}".format(e))


class GetSnapshotResults(Resource):
    """
    if user does not exist / snapshot does not exist / result does not exist, return 404.
    """
    def get(self, user_id, snapshot_id, result_name):

        parser_name = result_name.replace('-', '_')
        if parser_name not in RESULTS:
            logging.error("client attempted to access parser {} which does not exist".format(parser_name))
            abort(404)

        if not get_user(user_id):
            logging.error("User {} does not exist".format(user_id))
            abort(404)

        if not user_snapshot(user_id, snapshot_id):
            logging.error("Snapshot {} for User {} does not exist".format(snapshot_id, user_id))
            abort(404)

        result = parser_result(parser_name, user_id, snapshot_id)

        if not result:
            logging.error("result {} for snapshot {} for user {} does not exist"
                          .format(result_name, user_id, snapshot_id))
            abort(404)

        data = {}
        for key in result.keys():
            if key == "_id" or key in RESULTS_IGNORE[parser_name]:
                continue
            data[key] = result[key]
        results_add = RESULTS_ADD[parser_name]
        for key in results_add:
            if key == "data":
                data[key] = "{}/{}".format(request.base_url, results_add[key])
            else:
                data[key] = results_add[key]
        return data


class GetAdditionalData(Resource):
    """
    this class is used to retrieve the depth / color image (or additional data in the future) from the snapshots.

    """
    def get(self, user_id, snapshot_id, result_name, additional_data):
        parser_name = result_name.replace('-', '_')
        if parser_name not in RESULTS:
            logging.error("client attempted to access parser {} which does not exist".format(parser_name))
            abort(404)

        if not get_user(user_id):  # user does not exist in DB
            logging.error("User {} does not exist".format(user_id))
            abort(404)

        if not user_snapshot(user_id, snapshot_id):
            logging.error("Snapshot {} for User {} does not exist".format(snapshot_id, user_id))
            abort(404)

        result = parser_result(parser_name, user_id, snapshot_id)
        if not result:
            logging.error("result {} for snapshot {} for user {} does not exist"
                          .format(result_name, user_id, snapshot_id))
            abort(404)

        if additional_data == "data":
            data_path = result[PATHS[parser_name]]
            image_data = open(data_path, "rb").read()
            headers = {
                'Content-Type': 'application/octet-stream',
            }
            response = make_response(image_data)
            response.headers = headers
            return response


api_.add_resource(GetUsers, '/users')
api_.add_resource(GetUser, '/users/<user_id>')
api_.add_resource(GetUserSnapshots, '/users/<user_id>/snapshots')
api_.add_resource(GetSnapshotById, '/users/<user_id>/snapshots/<snapshot_id>')
api_.add_resource(GetSnapshotResults, '/users/<user_id>/snapshots/<snapshot_id>/<result_name>')
api_.add_resource(GetAdditionalData, '/users/<user_id>/snapshots/<snapshot_id>/<result_name>/<additional_data>')


def run_api_server(host, port, db_url):
    """
    initialize the logger and start the flask app.
    """
    init_logger()
    globals()["DB_CONNECTION"] = MongoClient(db_url)[DB_NAME]
    app.run(host=host, port=port)


def get_user(user_id):
    """
    Checks if user_id exists in the database, and return it.
    """
    try:
        collection = DB_CONNECTION["user_message"]
        search = {"user_id": int(user_id)}
        result = collection.find_one(search)
        return result

    except Exception as e:
        logging.error("Could not connect to DB: {}".format(e))
        abort(404)


def user_snapshot(user_id, snapshot_id):
    """
    check if snapshot_id exists for user_id and return it.
    """
    try:
        collection = DB_CONNECTION["snapshots"]
        search = {"user_id": user_id, "datetime": int(snapshot_id)}
        result = collection.find_one(search)
        return result

    except Exception as e:
        logging.error("Could not connect to DB: {}".format(e))
        abort(404)


def parser_result(parser_name, user_id, snapshot_id):
    """
    check if parser_name exists inside snapshot_it for user_id, and return it.
    """
    try:
        collection = DB_CONNECTION[parser_name]
        search = {"user_id": user_id, "datetime": int(snapshot_id)}
        result = collection.find_one(search)
        return result

    except Exception as e:
        logging.error("Could not connect to DB: {}".format(e))
        abort(404)


def exit_run():
    print("Error encountered. Please see log for details.")
    sys.exit(1)
