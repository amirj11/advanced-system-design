FROM ubuntu
RUN apt-get update
ENV DEBIAN_FRONTEND=noninteractive
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
RUN apt-get install -y python3.8 python3-pip
ADD cortex/ /cortex
ADD scripts/ /scripts
RUN /scripts/install.sh
CMD ["python3"]
