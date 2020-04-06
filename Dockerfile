FROM ubuntu
RUN apt-get update
ENV DEBIAN_FRONTEND=noninteractive
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
RUN apt-get install ttf-mscorefonts-installer -y
RUN apt install fontconfig -y
RUN fc-cache
RUN apt-get install -y python3.8 python3-pip
COPY cortex /cortex
COPY scripts /scripts
COPY requirements.txt /scripts/requirements.txt
RUN /scripts/install_docker.sh
CMD ["python"]
