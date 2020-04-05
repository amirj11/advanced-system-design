FROM ubuntu
RUN apt-get update
ENV DEBIAN_FRONTEND=noninteractive
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
RUN apt-get install -y python3.8 python3-pip
COPY cortex /cortex
COPY scripts /scripts
RUN /scripts/install_docker.sh
CMD ["python"]
