FROM python:3.8
LABEL maintainer="faisal.ajmal@gmail.com"

ADD ./shared /openlpr/shared
ADD ./platedetector /openlpr/platedetector
ADD ./shared/empty /filestorage/
ADD ./shared/empty /models/

WORKDIR /openlpr/platedetector

RUN sh -c "/openlpr/shared/install-python-deps.sh" && \
    pip3 install --no-cache-dir -r /openlpr/platedetector/requirements.txt

ENTRYPOINT [ "python3","/openlpr/platedetector/platedetector.py", "-mp", "/models/frozen_inference_graph.pb", "-lp", "/models/label_map.pbtxt"]