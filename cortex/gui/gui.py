import base64
from datetime import datetime
from flask import Flask, redirect, url_for, abort, make_response, render_template, send_file, Response, request
from flask_restful import Resource, Api, reqparse, request
import io
import json
import logging
import numpy as np
import os
import plotly
import plotly.graph_objs as go
from PIL import Image
from pymongo import MongoClient
import sys

app = Flask(__name__)
api_ = Api(app)

DB_NAME = "Cortex"
DB_CONNECTION = None
HOST = None
PORT = None

RESULTS = ["pose", "color_image", "depth_image", "feelings"]
FEELINGS = ["thirst", "happiness", "exhaustion", "hunger"]
DB_REMOVE = ["_id", "datetime", "user_id"]
IMAGES_TYPE = ["color_image", "depth_image", "translation"]
GENDER = {"0": "Male", "1": "Female", "2": "Other"}


def init_logger():
    """
    This function initializes the servers' logger. Logs will be save in Cortex/client/Logs directory.
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
                        filename='{}/server_{}.log'.format(dir_path, time_string), level=logging.DEBUG,
                        datefmt="%d.%m.%Y-%H:%M:%S")
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


@app.route('/', methods=['GET', 'POST'])
@app.route('/users', methods=['GET', 'POST'])
def index():
    collection = DB_CONNECTION["user_message"]
    data = []
    for user in collection.find({}, {"_id": 0, "user_id": 1, "username": 1}):
        print(user)
        user = {"username": user["username"], "user_id": user["user_id"]}
        data.append(user)
    return render_template('index.html', users=data)


@app.route("/users/<user_id>", methods=['GET'])
def user(user_id):
    result = get_user(user_id)
    if not result:
        logging.error("{}: {} ({})".format(request.remote_addr, request.url, "No user"))
        return render_template('error.html', error="No user with id {}".format(user_id))

    user_details = {}
    #  preparing user details to display in table
    user_details["User ID"] = result["user_id"]
    user_details["Gender"] = GENDER[str(result["gender"])]

    date_time = datetime.fromtimestamp(result["birthday"])
    user_details["Birthday"] = date_time.strftime("%d.%m.%Y")

    data = []
    for trace in get_feelings_list(user_id):
        data.append(trace)

    graphJSON = json.dumps(data, cls=plotly.utils.PlotlyJSONEncoder)

    images = {}
    collection = DB_CONNECTION["snapshots"]
    search = {"user_id": user_id}
    result = collection.find(search)
    for snapshot in result:
        images[snapshot["datetime"]] = get_image_url(user_id, snapshot["datetime"], "color_image")

    collection = DB_CONNECTION["user_message"]
    search = {"user_id": int(user_id)}
    result = collection.find_one(search)

    #names = ["thirst", "happiness", "exhaustion", "hunger", "translation"]
    return render_template('user.html', username=result["username"], user_id=user_id, graphJSON=graphJSON,
                           images=images, graphs_names=FEELINGS, user_details=user_details)


@app.route("/users/<user_id>/user_pose")
def display_pose_image(user_id):
    pose_img = get_pose_graph(user_id)


@app.route("/users/<user_id>/snapshots", methods=['GET', 'POST'])
def snapshots(user_id):
    args = request.args
    user = get_user(user_id)
    if not user:
        logging.error("{}: {} ({})".format(request.remote_addr, request.url, "No user"))
        return render_template('error.html', error="No user with id {}".format(user_id))

    if "page" not in args:
        page = 1
    else:
        page = int(args["page"])

    last_page = 0

    all_snapshots = get_snapshots(user_id)
    some_snapshots = all_snapshots[10*(page-1):10*(page-1)+10]
    print(some_snapshots)
    data = {}
    times = {}
    images = {}
    empty_page = 1
    for snapshot in some_snapshots:
        empty_page = 0
        images[snapshot["datetime"]] = get_image_url(user_id, snapshot["datetime"], "color_image")
        times[snapshot["datetime"]] = snapshot["time_string"]
        parsers = []
        for parser in RESULTS:
            collection = DB_CONNECTION[parser]
            search = {"user_id": user_id, "datetime": int(snapshot["datetime"])}
            result = collection.find_one(search)
            if result:
                parsers.append(parser.replace('_', '-'))
        data[snapshot["datetime"]] = parsers

    return render_template('snapshots.html', username=user["username"], user_id=user_id, snapshots=data, times=times,
                           images=images, page_num=page, empty_page=empty_page)


@app.route("/users/<user_id>/snapshots/<snapshot_id>")
def snapshot_summary(user_id, snapshot_id):
    user = get_user(user_id)
    if not user:
        logging.error("{}: {} ({})".format(request.remote_addr, request.url, "No user"))
        return render_template('error.html', error="No user with id {}".format(user_id))

    snapshot_ = get_snapshot(user_id, snapshot_id)
    if not snapshot_:
        logging.error("{}: {} ({})".format(request.remote_addr, request.url, "No snapshot for user"))
        return render_template('error.html', error="No snapshot {} for user {}".format(snapshot_id, user_id))

    results_dict = {}
    for parser in RESULTS:
        collection = DB_CONNECTION[parser]
        search = {"user_id": user_id, "datetime": int(snapshot_["datetime"])}
        result = collection.find_one(search)
        if result:
            for item in DB_REMOVE:
                if item in result.keys():
                    del result[item]
            if parser in IMAGES_TYPE:
                result = change_image_result(parser, result, user_id, snapshot_id)
            if parser == "pose":
                result = change_pose_result(result, user_id, snapshot_id)
            results_dict[parser] = result

    return render_template('snapshot_summary.html', username=user["username"], snapshot_id=snapshot_id, user_id=user_id,
                           parsers=results_dict)


@app.route("/users/<user_id>/snapshots/<snapshot_id>/<image_type>")
def show_image(user_id, snapshot_id, image_type):
    image_type = image_type.replace('-', '_')
    if image_type not in IMAGES_TYPE:
        logging.error("{}: {} ({})".format(request.remote_addr, request.url, "no such data type"))
        return render_template('error.html', error="Unknown data type: {}".format(image_type))

    if image_type == "color_image" or image_type == "depth_image":
        collection = DB_CONNECTION[image_type]
        search = {"user_id": user_id, "datetime": int(snapshot_id)}
        result = collection.find_one(search)
        if not result:
            logging.error("{}: {} ({})".format(request.remote_addr, request.url, "no data type for snapshot"))
            return render_template('error.html', error="No {} result for snapshot {} of user {}"
                                   .format(image_type, snapshot_id, user_id))
        image_path = result["{}_path".format(image_type)]
        print(image_path)
        img = Image.open(image_path)
        return serve_pil_image(img)

    elif image_type == "translation":
        collection = DB_CONNECTION["pose"]
        search = {"user_id": user_id, "datetime": int(snapshot_id)}
        result = collection.find_one(search)
        path = result["translation_path"]
        img = Image.open(path)
        return serve_pil_image(img)


def run_server(host, port, database_url):
    init_logger()
    globals()["DB_CONNECTION"] = MongoClient(database_url)[DB_NAME]
    try:
        db_test = globals()["DB_CONNECTION"]["test"]

    except Exception as e:

        message = "Could not connect to DB: {}".format(e)
        logging.error(message)
        print(message)
        sys.exit(1)

    globals()["HOST"] = host
    globals()["PORT"] = port
    app.run(host=host, port=port)


def get_user(user_id):
    """
    Checks if user_id exists in the database.
    """
    try:
        collection = DB_CONNECTION["user_message"]
        search = {"user_id": int(user_id)}
        result = collection.find_one(search)
        return result

    except Exception as e:
        message = "Could not connect to DB: {}".format(e)
        logging.error(message)
        return render_template('error.html', error="Could not connect to DB.")


def get_snapshot(user_id, snapshot_id):
    try:
        collection = DB_CONNECTION["snapshots"]
        search = {"user_id": user_id, "datetime": int(snapshot_id)}
        result = collection.find_one(search)
        return result

    except Exception as e:
        message = "Could not connect to DB: {}".format(e)
        logging.error(message)
        return render_template('error.html', error="Could not connect to DB.")


def get_snapshots(user_id):
    try:
        collection = DB_CONNECTION["snapshots"]
        search = {"user_id": user_id}
        result = collection.find(search).sort("datetime")
        return result

    except Exception as e:
        message = "Could not connect to DB: {}".format(e)
        logging.error(message)
        return render_template('error.html', error="Could not connect to DB.")


def get_image_url(user_id, snapshot_id, image_type):
    image_type = image_type.replace('_', '-')
    server_url = "http://{}:{}".format(HOST, PORT)
    return "{}/users/{}/snapshots/{}/{}".format(server_url, user_id, snapshot_id, image_type)


def serve_pil_image(pil_img):
    img_io = io.BytesIO()
    pil_img.save(img_io, 'JPEG', quality=70)
    img_io.seek(0)
    return send_file(img_io, mimetype='image/jpeg')


def change_image_result(parser_name, result, user_id, snapshot_id):
    del result["{}_path".format(parser_name)]
    result["image_path"] = get_image_url(user_id, snapshot_id, parser_name)
    return result


def change_pose_result(result, user_id, snapshot_id):
    result["translation_path"] = get_image_url(user_id, snapshot_id, "translation")
    return result


def get_feelings_list(user_id):
    collection = DB_CONNECTION["feelings"]
    search = {"user_id": user_id}
    feelings_list = []

    for feeling in FEELINGS:
        x_data = []
        y_data = []
        for result in collection.find(search, {feeling: 1, "datetime": 1}).sort("datetime"):
            x_data.append(int(result["datetime"]))
            y_data.append(float(result[feeling]))

        layout = go.Layout(
            autosize=False,
            width=500,
            height=500,
            margin=go.layout.Margin(
                l=50,
                r=50,
                b=100,
                t=100,
                pad=3
            ),
            paper_bgcolor='#f0e2c8',
            plot_bgcolor='#c7c7c7',
            title=feeling,
        )

        trace = {"data": {"x": x_data, "y": y_data, "type": "line"}, "layout": layout}
        feelings_list.append(trace)

    return feelings_list


def get_pose_data(user_id):
    try:

        collection = DB_CONNECTION["pose"]
        search = {"user_id": user_id}
        result = collection.find(search).sort("datetime")
        timestamps = []
        data_x = []
        data_y = []
        data_z = []
        for snapshot in result:
            timestamps.append(snapshot["datetime"])
            data_x.append(snapshot["translation_x"])
            data_y.append(snapshot["translation_y"])
            data_z.append(snapshot["translation_z"])

        # data_x = {snapshot["datetime"]: snapshot["translation_x"] for snapshot in result}
        # data_y = {snapshot["datetime"]: snapshot["translation_y"] for snapshot in result}
        # data_z = {snapshot["datetime"]: snapshot["translation_z"] for snapshot in result}
        return timestamps, data_x, data_y, data_z

    except Exception as e:
        message = "Could not connect to DB: {}".format(e)
        logging.error(message)
        return render_template('error.html', error="Could not connect to DB.")


def get_pose_graph(user_id):
    x, y, z = np.random.multivariate_normal(np.array([0, 0, 0]), np.eye(3), 200).transpose()
    layout = go.Layout(
        autosize=False,
        width=500,
        height=500,
        margin=go.layout.Margin(
            l=50,
            r=50,
            b=100,
            t=100,
            pad=3
        ),
        paper_bgcolor='#f0e2c8',
        plot_bgcolor='#c7c7c7',
        title="translation",
    )
    # fig = go.Figure(data=[trace1], layout=layout)
    fig = dict(data=[go.Scatter3d(x=x, y=y, z=z,
                                   mode='markers')], layout=layout)
    return fig

