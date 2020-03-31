import base64
from flask import Flask, redirect, url_for, abort, make_response, render_template, send_file, Response
from flask_restful import Resource, Api, reqparse, request
import io
import json
import plotly
import plotly.graph_objs as go
from PIL import Image
from pymongo import MongoClient
import numpy as np


app = Flask(__name__)
api_ = Api(app)

DB_NAME = "Cortex"
DB_CONNECTION = None
HOST = None
PORT = None

RESULTS = ["pose", "color_image", "depth_image", "feelings"]
FEELINGS = ["thirst", "happiness", "exhaustion", "hunger"]
DB_REMOVE = ["_id", "datetime", "user_id"]
IMAGES_TYPE = ["color_image", "depth_image"]


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
        abort(404)

    # collection = DB_CONNECTION["feelings"]
    # search = {"user_id": user_id}
    # x_data = []
    # y_data = []
    # for result in collection.find(search, {"thirst": 1, "datetime": 1}):
    #     x_data.append(int(result["datetime"]))
    #     y_data.append(float(result["thirst"]))
    # print(x_data)
    # print("---")
    # print(y_data)
    # # trace = go.Scatter(
    # #     x = x_data,
    # #     y = y_data
    # # )
    # #trace = {"data": [x_data, y_data], "layout": {"title": "graph"}}
    # layout = go.Layout(
    #     autosize=False,
    #     width=500,
    #     height=500,
    #     margin=go.layout.Margin(
    #         l=50,
    #         r=50,
    #         b=100,
    #         t=100,
    #         pad=3
    #     ),
    #     paper_bgcolor='#7f7f7f',
    #     plot_bgcolor='#c7c7c7',
    #     title="Thirst",
    # )
    # trace = {"data": {"x": x_data, "y": y_data, "type": "line"}, "layout": layout}
    # # trace = go.Scatter(
    # #     x=x_data,
    # #     y=y_data,
    # # )
    # data = [trace]
    data = []
    for trace in get_feelings_list(user_id):
        data.append(trace)
    data.append(get_pose_graph(user_id))
    # data = get_feelings_list(user_id)
    # data = data.append(get_pose_graph(user_id))
    print(data)
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

    names = ["thirst", "happiness", "exhaustion", "hunger", "translation"]
    return render_template('user.html', username=result["username"], user_id=user_id, graphJSON=graphJSON,
                           images=images, graphs_names=names)


# @app.route("/users/<user_id>/user_pose")
# def display_pose_image(user_id):
#     pose_img = generate_pose_image(user_id)
#     output = io.BytesIO()
#     plt.savefig(output, format='png')
#     output.seek(0)
#     plot_url = base64.b64encode(output.getvalue()).decode()
#     display = mpld3.fig_to_html(pose_img, use_http=True)
#     #return '<img src="data:image/png;base64,{}">'.format(plot_url)
#     return display
#     #FigureCanvas(pose_img).print_png(output)
#     #return Response(output.getvalue(), mimetype='image/png')

@app.route("/users/<user_id>/user_pose")
def display_pose_image(user_id):
    pose_img = get_pose_graph(user_id)


@app.route("/users/<user_id>/snapshots")
def snapshots(user_id):
    user = get_user(user_id)
    if not user:
        abort(404)

    all_snapshots = get_snapshots(user_id)
    data = {}
    times = {}
    for snapshot in all_snapshots:
        times[snapshot["datetime"]] = snapshot["time_string"]
        parsers = []
        for parser in RESULTS:
            collection = DB_CONNECTION[parser]
            search = {"user_id": user_id, "datetime": int(snapshot["datetime"])}
            result = collection.find_one(search)
            if result:
                parsers.append(parser.replace('_', '-'))
        data[snapshot["datetime"]] = parsers

    return render_template('snapshots.html', username=user["username"], user_id=user_id, snapshots=data, times=times)


@app.route("/users/<user_id>/snapshots/<snapshot_id>")
def snapshot(user_id, snapshot_id):

    user = get_user(user_id)
    if not user:
        abort(404)

    snapshot_ = get_snapshot(user_id, snapshot_id)
    if not snapshot_:
        abort(404)

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
            results_dict[parser] = result

    return render_template('snapshot.html', username=user["username"], user_id=user_id, snapshot_id=snapshot_id,
                           parsers=results_dict)


@app.route("/users/<user_id>/snapshots/<snapshot_id>/<image_type>")
def show_image(user_id, snapshot_id, image_type):
    image_type = image_type.replace('-', '_')
    if image_type not in IMAGES_TYPE:
        abort(404)
    collection = DB_CONNECTION[image_type]
    search = {"user_id": user_id, "datetime": int(snapshot_id)}
    result = collection.find_one(search)
    if not result:
        abort(404)
    image_path = result["{}_path".format(image_type)]
    img = Image.open(image_path)
    return serve_pil_image(img)


def run_server(host, port, database_url):
    print("in run server")
    globals()["DB_CONNECTION"] = MongoClient(database_url)[DB_NAME]
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
        abort(404)


def get_snapshot(user_id, snapshot_id):
    try:
        collection = DB_CONNECTION["snapshots"]
        search = {"user_id": user_id, "datetime": int(snapshot_id)}
        result = collection.find_one(search)
        return result

    except Exception as e:
        abort(404)


def get_snapshots(user_id):
    try:
        collection = DB_CONNECTION["snapshots"]
        search = {"user_id": user_id}
        result = collection.find(search).sort("datetime")
        return result

    except Exception as e:
        abort(404)


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
        abort(404)


def get_pose_graph(user_id):
    x, y, z = np.random.multivariate_normal(np.array([0, 0, 0]), np.eye(3), 200).transpose()
    # trace1 = dict(
    #     type='scatter',
    #     x=x,
    #     y=y,
    #     z=z,
    #     # mode='markers',
    #     # marker=dict(
    #     #     size=12,
    #     #     line=dict(
    #     #         color='rgba(217, 217, 217, 0.14)',
    #     #         width=0.5
    #     #     ),
    #     #     opacity=0.8
    #     # )
    # )
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

# def get_pose_graph(user_id):
#     timestamps, data_x, data_y, data_z = get_pose_data(user_id)
#     start_timestamp = timestamps[0]
#     x = [data_x[0]]
#     y = [data_y[0]]
#     z = [data_z[0]]
#
#     first_spot = go.Scatter3d(
#         x=x,
#         y=y,
#         z=z,
#         mode='markers',
#         marker=dict(
#             size=12,
#             line=dict(
#                 color='rgba(217, 217, 217, 0.14)',
#                 width=0.5
#             ),
#             opacity=0.8
#         )
#     )
#
#     x2 = data_x[1:]
#     y2 = data_y[1:]
#     z2 = data_z[1:]
#
#     next_spots = go.Scatter3d(
#         x=x2,
#         y=y2,
#         z=z2,
#         mode='markers',
#         marker=dict(
#             color='rgb(127, 127, 127)',
#             size=12,
#             symbol='circle',
#             line=dict(
#                 color='rgb(204, 204, 204)',
#                 width=1
#             ),
#             opacity=0.9
#         )
#     )
#
#     data = [first_spot, next_spots]
#
#     layout = go.Layout(
#         margin=dict(
#             l=0,
#             r=0,
#             b=0,
#             t=0
#         )
#     )
#
#     trace = {"data": data, "layout": layout}
#     return trace


# def generate_pose_image(user_id):
#     timestamps, data_x, data_y, data_z = get_pose_data(user_id)
#
#     fig = plt.figure()
#     plt.subplots_adjust(bottom=0.25)
#     graph = fig.add_subplot(122, projection='3d')
#     start_timestamp = timestamps[0]
#     end_timestamp = timestamps[-1]
#     print(list(data_x.values()))
#     graph.set_xlim(min(list(data_x.values())), max(list(data_x.values())))
#     graph.set_ylim(min(list(data_y.values())), max(list(data_y.values())))
#     graph.set_zlim(min(list(data_z.values())), max(list(data_z.values())))
#     graph.scatter(data_x[start_timestamp], data_y[start_timestamp], data_z[start_timestamp])
#
#     # Slider settings
#     slider_axis = plt.axes([0.2, 0.1, 0.65, 0.03])
#     slider = Slider(slider_axis, 'Snapshot ID', start_timestamp, end_timestamp, valinit=start_timestamp)
#
#     def update(val):
#         value = slider.val
#         graph.clear()
#         x_value = data_x[value]
#         y_value = data_x[value]
#         z_value = data_z[value]
#         graph.scatter([x_value], [y_value], [z_value])
#         graph.set_xlim(min(list(data_x.values())), max(list(data_x.values())))
#         graph.set_ylim(min(list(data_y.values())), max(list(data_y.values())))
#         graph.set_zlim(min(list(data_z.values())), max(list(data_z.values())))
#         fig.canvas.draw_idle()
#
#     slider.on_changed(update)
#
#     return fig
