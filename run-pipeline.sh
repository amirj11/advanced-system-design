docker build --no-cache -t cortex .
docker network create -d bridge cortexnet

docker run -d --network cortexnet --hostname=db --name=db mongo
docker run -d --network cortexnet --hostname=mq --name=mq rabbitmq:3-management
sleep 60
docker run -d -v cortex:/cortex --network cortexnet --hostname=server --name=server -p 8000:8000 cortex python3 -m cortex.server run-server -h '0.0.0.0' -p 8000 'mq'
docker run -d -v cortex:/cortex --network cortexnet --hostname=pose --name=pose cortex python3 -m cortex.parsers run-parser 'pose' 'mq'
docker run -d -v cortex:/cortex --network cortexnet --hostname=color --name=color cortex python3 -m cortex.parsers run-parser 'color_image' 'mq'
docker run -d -v cortex:/cortex --network cortexnet --hostname=depth --name=depth cortex python3 -m cortex.parsers run-parser 'depth_image' 'mq'
docker run -d -v cortex:/cortex --network cortexnet --hostname=feelings --name=feelings cortex python3 -m cortex.parsers run-parser 'feelings' 'mq'
docker run -d -v cortex:/cortex --network cortexnet --hostname=saver --name=saver cortex python3 -m cortex.saver run-saver "mongodb://db:27017" 'mq'
docker run -d -v cortex:/cortex --network cortexnet --hostname=api --name=api -p 5000:5000 cortex python3 -m cortex.api run-server -h "0.0.0.0" -p 5000 -d "mongodb://db:27017"
docker run -d -v cortex:/cortex --network cortexnet --hostname=gui --name=gui -p 8080:8080 cortex python3 -m cortex.gui run-server -h "0.0.0.0" -p 8080 -d "mongodb://db:27017"
