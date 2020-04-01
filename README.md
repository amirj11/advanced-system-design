# Cortex
Cortex is a system which lets a client upload a file of "snapshots" of himself to a server. the snapshots are then passed to a message-queue, parsed, saved in a DB and can be queried via API, CLI or GUI.

## Overview
The system contains the following components: (orange = server side, green = client side)

![overview image](https://raw.githubusercontent.com/amirj11/advanced-system-design/master/docs/overview.jpg)

each server side component has its own Docker.

## Installation & Deployment
run the following commands to deploy the project:
```bash
./scripts/install.sh
source .env/bin/activate
```


# System Components

### Snapshots File
the snapshots file is a gzipped binary containing a sequence of messages, serialized with ProtoBuf (format in cortex/client/cortex.proto). it starts with a User message, defining the user who uploads the file (his name, user id, gender and birthday). after the User message there is a sequence of Snapshot messages, each containing:
- snapshot timestamp (with milliseconds)
- pose (floats; the user location in 3D and head tilt)
- color image (binary sequence; what the user was seeing in this snapshot)
- depth image (binary sequence: a heatmap showing how far objects are from the user in this snapshot)
- feelings (floats from -1 to 1: the users' thirst, exhaustion, hunger and happiness levels)

### Client

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

### Server
the server is a based on Flask and Flask-Restful. 
it is initiated with a host, a port, and a publish method (function, in API) or a message-queue URL (in CLI). messages results from the server can either be sent to a function provided by the user, or to a message queue.
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
    -p/--port 8000 'rabbitmq://127.0.0.1:5672/'
```

### RabbitMQ (Message Queue)
The message queue is just a Docker running RabbitMQ.

### Parsers
Parsers can run as a one-time script (receiving a parser name and data to parse), or as a service (connecting to MQ and consuming from it indefinitely).
Parsers are functions. When initiated, the 'parsers' module connects to the MQ, passes messages to the correct parser function, and publishes the result which the parser returns. each parser initialization loads another instance of the 'parsers' module.
The module connects to the 'snapshpt' exchange name ('direct' exchange type), and uses the parser function as a callback method for when a message arrives.
The result from the parser is then sent to the 'processed_data' exchange name ('topic' exchange type), with the parsers' name as the topic. This data is received by the Saver.
The parsers receive raw data in JSON the publish back JSON.
Each parser receives the entire snapshot data and extracts relevant data from it.

#### Adding a new parser type
Adding new types of parsers is very easy. Follow these steps:
1. open cortex/parsers/parsers.py
2. write your parsing function which accepts a single argument (for data). The data will be passed to you parser in JSON string format, with values as documented in the "snapshot_to_json" function of cortex/server/server.py
3. decorate it with "@parser". this will log your parser with all the other parsers and allow the wrapper to use it.
4. return your desired result. the parsers service will receive it, dump it into JSON string and publish it back to the MQ, with the topic being your new parsers name.
5. that is it! you can not deploy your parser (see API and CLI later on)


##### Pose Parser ('pose')
extracts pose data from snapshot (3D user location, head tilt) into a smaller JSON message. result values:
- user id
- snapshot timestamp
- Translation: x, y, z
- Rotation: x, y, z, w

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
python -m cortex.parsers run-parser 'pose' 'rabbitmq://127.0.0.1:5672/'
```

