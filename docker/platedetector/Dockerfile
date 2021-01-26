FROM openlpr/base-image:2.0
LABEL maintainer="faisal.ajmal@gmail.com"

ADD ./platedetector /openlpr/platedetector
WORKDIR /openlpr/platedetector

ENTRYPOINT [ "python3","/openlpr/platedetector/platedetector.py", "-mp", "/models/frozen_inference_graph.pb", "-lp", "/models/label_map.pbtxt"]