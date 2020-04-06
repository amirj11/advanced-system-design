# Cortex
Cortex is a system which lets a client upload a file of "snapshots" of himself to a server. the snapshots are then passed to a message-queue, parsed, saved in a DB and can be queried via API, CLI or GUI.
The system can be automatically deployed with multiple Dockers.

[![Build Status](https://travis-ci.org/amirj11/advanced-system-design.svg?branch=master)](https://travis-ci.org/github/amirj11/advanced-system-design)

## Table of Contents

- [Cortex](#cortex)
  * [Overview](#overview)
  * [Installation & Deployment](#installation---deployment)
    + [Logging](#logging)
    + [Testing](#testing)
- [System Components](#system-components)
    + [0. Snapshots File](#0-snapshots-file)
    + [1. Client](#1-client)
    + [2. Server](#2-server)
        * [Server pusblishing to Message-Queue](#server-pusblishing-to-message-queue)
    + [3. RabbitMQ (Message Queue)](#3-rabbitmq--message-queue-)
    + [4. Parsers](#4-parsers)
        * [Adding a new parser type](#adding-a-new-parser-type)
        * [Pose Parser ('pose')](#pose-parser---pose--)
        * [Color Image Parser ('color_image'), Depth Image Parser ('depth_image')](#color-image-parser---color-image----depth-image-parser---depth-image--)
        * [Feelings Parser ('feelings')](#feelings-parser---feelings--)
    + [5. Saver](#5-saver)
    + [6. Database](#6-database)
    + [7. API](#7-api)
    + [8. CLI](#8-cli)
    + [9. GUI](#9-gui)
  * [Protocol Summary](#protocol-summary)
  * [MQ Communication Summary](#mq-communication-summary)
- [Automatic Deployment (using Dockers)](#automatic-deployment--using-dockers-)

<small><i><a href='http://ecotrust-canada.github.io/markdown-toc/'>Table of contents generated with markdown-toc</a></i></small>


## Overview
The system contains the following components: (orange = server side, green = client side)

![overview image](https://raw.githubusercontent.com/amirj11/advanced-system-design/master/docs/overview.jpg)

each server side component has its own Docker.

## Installation & Deployment
run the following commands to install dependencies and enter the virtual environment:
```bash
./scripts/install.sh
source .env/bin/activate
```
The installation requires Python 3.8.0.

### Logging
All system components use 'logging' package to log their runtime errors and some of their regular runtime operations. logs will be saved in "Logs" directory which will be created inside each of the components' directories.

### Testing
The project has a tests directory under cortex/tests. The project is intergated with Travis-CI so that every push runs all project tests. Click the projects' Travis-CI badge at the beginning of this file for more details.

# System Components
 The system components are subpackages of the main project package.
### 0. Snapshots File
the snapshots file is a gzipped binary containing a sequence of messages, serialized with ProtoBuf (format in cortex/client/cortex.proto). it starts with a User message, defining the user who uploads the file (his name, user id, gender and birthday). after the User message there is a sequence of Snapshot messages, each containing:
- snapshot timestamp (with milliseconds)
- pose (floats; the user location in 3D and head tilt)
- color image (binary sequence; what the user was seeing in this snapshot)
- depth image (binary sequence: a heatmap showing how far objects are from the user in this snapshot)
- feelings (floats from -1 to 1: the users' thirst, exhaustion, hunger and happiness levels)

Before each message is its size in bytes, so the snapshot binary file format is:
(user message size)(user message)(snapshot #1 message size)(snapshot 1)(snapshot #2 message size)(snapshot 2), etc.
### 1. Client

the client is initiated with a server ip, server port and a path to a "snapshots" file. it reads the snapshot file one message at a time (not reading all of it into memory at once), deserializes the message, re-serializes it to the same ProtoBuf protocol and sends it to the servers' REST APi using an HTTP POST request.
the de-serialization and re-serlialization of the message may seem unnecessary because it's from and to the same format, but it decouples the client-server protocol from the files' format. this way, if the serialization format of the file changes, only the de-serialization in the client will change, but it will always re-serialize the data to the original ProtoBuf format. There will be no need for changes in the client-server protocol.

The client exposes a Python API:
```python
from cortex.client import upload_sample
upload_sample(host='127.0.0.1', port=8000, path='sample.mind.gz')
```
and a CLI:
```bash
python -m cortex.client upload-sample -h/--host '127.0.0.1' \
    -p/--port 8000 'sample.mind.gz'
```

### 2. Server
the server is a based on Flask and Flask-Restful. 
it is initiated with a host, a port, and a publish method (function, in API) or a message-queue URL (in CLI). messages results from the server can either be sent to a function provided by the user, or to a message queue.

The server exposes a RESTful API to clients. this means that no one client is holding the entire server until it finishes. multiple client can send snapshot messages to the server at once.
API routes for use by the Client:
- User messages will be accepted at "api/user_message/<user_id>"
- Snapshot messages will be accepted at "/api/snapshot_message/<user_id>"

The server de-serializes each message type (User or Snapshot) according to the ProtoBuf format, and re-serializes it into JSON. raw binary data (such as the color image and depth image) will be saved to a file on disk, and only its path will be included in the JSON message, so as to not include large binary data in JSON. the JSON message will be dumped to a string and sent to the desired publishing method (function or queue).
This is the last point in the project which uses the ProtoBuf format.
##### Server pusblishing to Message-Queue
The server sends User and Snapshot JSON messages differently, using the Python 'pika' package for RabbitMQ. User messages do not need parsing and they go from the MQ directly to the saver. Snapshot messages go to the parsers first, and only then to the saver.
- User messages: 'topic' exchange type, exchange name 'processed_data' (which the saver subscribes to and consumes from)
- Snapshot messages: 'direct' exchange type, exchange name 'snapshot'. every parser will open its' own queue, bind itself to the 'snapshot' exchange and receive each snapshot. the server includes the user_id into every snapshot because raw snapshots do not include this information.

This way, the server does not know about the parsers directly. the 'snapshot' direct exchange separates the server from parsers.

The server exposes a Python API:
```python
from cortex.server import run_server
def print_message(message):
    print(message)
run_server(host='127.0.0.1', port=8000, publish=print_message)
```

and a CLI:
```bash
python -m cortex.server run-server -h/--host '127.0.0.1' \
    -p/--port 8000 'rabbitmq://127.0.0.1:5672'
```

### 3. RabbitMQ (Message Queue)
- The message queue is just a running RabbitMQ service (or Docker in the Automatic docker deployment).
- The components which use the MQ (Server, Parsers, Saver) have their MQ-related  code concentrated in wrappers and publishing function, which makes adding support for other types of MQs very easy. They already know that they work with "RabbitMQ", and won't accept any other MQ URL.

### 4. Parsers
- Parsers can run as a one-time script (receiving a parser name and data to parse), or as a service (connecting to MQ and consuming from it indefinitely).
- Parsers are functions. When initiated, the 'parsers' module connects to the MQ, passes messages to the correct parser function, and publishes the result which the parser returns. each parser initialization loads another instance of the 'parsers' module.
- The module connects to the 'snapshpt' exchange name ('direct' exchange type), and uses the parser function as a callback method for when a message arrives.
The result from the parser is then sent to the 'processed_data' exchange name ('topic' exchange type), with the parsers' name as the topic. This data is received by the Saver.
- The parsers receive raw data in JSON the publish back JSON messages.
- Each parser receives the entire snapshot data and extracts relevant data from it.
- Several parsers of the same type can be initiated to perform load-balancing.

##### Adding a new parser type
Adding new types of parsers is very easy. Follow these steps:
1. open cortex/parsers/parsers.py
2. write your parsing function which accepts a single argument (for data). The data will be passed to you parser in JSON string format, with values as documented in the "snapshot_to_json" function of cortex/server/server.py
3. decorate it with "@parser". this will log your parser with all the other parsers and allow the wrapper to use it.
4. return your desired result. the parsers service will receive it, dump it into JSON string and publish it back to the MQ, with the topic being your new parsers name.
5. that is it! you can not deploy your parser (see API and CLI later on)


##### Pose Parser ('pose')
extracts pose data from snapshot (3D user location, head tilt) into a smaller JSON message, saves the user 3d location and head tilt as pictures. result values:
- user id
- snapshot timestamp
- Translation: x, y, z
- Rotation: x, y, z, w
- paths to rotation and translation images

##### Color Image Parser ('color_image'), Depth Image Parser ('depth_image')
extract image data (color image or depth image) from snapshot (image height, width), oreads the raw binary data from disk and converts it to a real image using PIL, and saves the processed image to disk.
result values:
- user id
- snapshot timestamp
- image size: height, width
- path to the file containing the processes .jpg image.

##### Feelings Parser ('feelings')
extracts feelings from snapshot.
result values:
- user id
- snapshot timestamp
- hunger
- thirst
- exhaustion
- happiness

The parsers module exposes a Python API which runs the parser once:
```python
from cortex.parsers import run_parser
data = ... #  JSON String
result = run_parser('pose', data)
```

and a CLI:
running once and saving results to file:
'snapshot.raw' is a path to a file containing the data.
```bash
pythom -m cortex.parsers parse 'pose' 'snapshot.raw' > 'pose.result'
```

running as a service:
```bash
python -m cortex.parsers run-parser 'pose' 'rabbitmq://127.0.0.1:5672'
```

### 5. Saver
the saver receives process data from the MQ and saves it to a DB. This project uses MongoDB as the back-end, using 'pymongo' package, and can run once or as a service.
It is initiated with a URL for the DB, and a URL for the MQ (if run as a service).
As a service, the saver connects to the RabbitMQs' 'processed_data' exchange ('topic' exchange type), and binds to the following topics:
- user_message (user messages from the Server)
- pose
- color_image
- depth_image
- feelings
Binding to individual topics allows to add another component in parallel to the Saver, which can declare which data it wants to receive, instead of receiving all data as default.
Whenever a message arrives on the queue, the callback function creates a "Saver" class instance and calls its 'save' method with the data received and the topic through which the message has arrived.
Before saving data to the DB, the Saver verifies the data is not duplicated (i.e there isn't already such user, or that a certain parser result isn't already documented for a specific user with a specific snapshot timestamp). if not, it saves the data to the DB.

The Saver exposes a Python API:
```python
from cortex.saver import Saver
saver = Saver(database_url)
data = ...  #  JSON String
saver.save('color_image', data)
```

 and a CLI:
 run once:
 ```bash
 python -m cortex.saver save -d/--database 'mongodb://127.0.0.1:27017/' \
    'color_image' 'color.data'
```
run as a service:
```bash
python -m cortex.saver run-saver 'mongodb://127.0.0.1:27017/' \
    'rabbitmq://127.0.0.1:5672'
```

### 6. Database
The database is a running MongoDB service (or Docker in the Auto docker deployment).
it contains the following collections:
1. "user_message": users information, including user id, username, birthday and gender
2. "snapshots": list of snapshots with only timestamp and user id
3. collection for each parser: pose, color image, depth image, feelings. these collection contain the user id and snapshot timestamp as well as the processed results from each parser.


### 7. API
The API exposes a RESTful API to query the database
It is a Flask server with Flask-Restful, using 'pymongo' to query the DB.

Supported endpoints:
- GET /users - a list of all documented users with their user ids and names.
- GET /users/user-id - returns the user-id details: name, birthday and gender.
- GET /users/user-id/snapshots - returns a list of documented snapshots with their timestamps only.
- GET /users/user-id/snapshots/snapshot-id - returns the snapshot details - timestamp, supported results (documented parsers results for this snapshot).
- GET /users/user-id/snapshots/snapshot-id/result-name - returns the specified parsers' results for this snapshot. for binary data (color and depth image) it returns the path to getting the actual binary data.
- GET /users/user-id/snapshots/snapshot-id/color-image/data - returns the binary data of the image (supported for 'color-image' and 'depth-image')

the API exposes a Python API:
```python
from cortex.api import run_api_server
run_api_server(host="127.0.0.1", port=5000, database_url="mongodb://127.0.0.1:27017/")
```

and a CLI:
```bash
python -m cortex.api run-server -h/--host "127.0.0.1" -p/--port 8000 -d/--database 'mongodb://127.0.0.1:27017/'
```

### 8. CLI
the CLI is a tool which consumes the API. it provides the user a way to send requests to the API.
all CLI commands accept the -h/--host and -p/--port flags to configure the API address, but contain default values.
The get-result command accepts the -s/--save flag that receives a path and saves the result to it.

Available commands:
```bash
python -m cortex.cli get-users
python -m cortex.cli get-user <user_id>
python -m cortex.cli get-snapshots <user_id>
python -m cortex.cli get-snapshot <user_id> <snapshot_id>
python -m cortex.cli get-result <user_id> <snapshot_id> <parser_name>
```

### 9. GUI
The GUI is based on Flask and Flask-Restful.
I've put most of the focus on the feelings since they can summarize what the user was experiencing througout the sample.
1. inside the main users' page you will see 4 interactive graphs, one for each feeling.
2. **clicking on a certain point inside a graph will open the color image the user was seeing at that moment - making it extremely easy to understand why the users' feelings are changing.**
3. You can also get a full list of user snapshots, and inside each snapshots' page you will find a snapshot summary (including the color image, depth image, user location etc) and the raw data of the snapshot as saved in the DB.

The GUI exploses a Python API:
```python
from cortex.gui import run_server
run_server(host='127.0.0.1', port=8080, database_url='mongodb://127.0.0.1/27017/')
```

and a CLI:
```bash
python -m cortex.gui run-server -h/--host '127.0.0.1' -p/--port 8080 -d/--database 'mongodb://127.0.0.1/27017/'
```

## Protocol Summary
This layout shows which protocol is used between all components:

![protocols image](https://raw.githubusercontent.com/amirj11/advanced-system-design/master/docs/protocols.jpg)

## MQ Communication Summary
This layout shows a summary of communication through the RabbitMQ:

![mq image](https://raw.githubusercontent.com/amirj11/advanced-system-design/master/docs/mq.jpg)

# Automatic Deployment (using Dockers)
The system can be quickly deployed using Dockers by running the pre-configured deployment script: run-pipeline.sh
This script will: 
1. Build a Docker image based on Ubuntu with the project directory and all dependencies already inside.
2. Deploy each system component (Server, MQ, Parsers, Saver, DB, API and GUI) in its own Docker.
3. All Dockers will use a shared directory (volume) in which the raw binary data and final processed images will be saved.
4. All Dockers will share a dedicated network.
5. Multiple depth-image parsers will be deployed to demonstrate load-balancing between same types of parsers.

Some Dockers will be accessible from your host machine:

* Server: localhost:8000
* API: localhost:5000
* GUI: http://localhost:8080

After deployment you can start uploading sample files from the client to the server (after running the installation script on your host), and watch the results in the GUI or get them with the CLI.
The deployment script may take several minutes to finish preparing the system and build the project image.
