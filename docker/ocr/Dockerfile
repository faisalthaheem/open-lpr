FROM openlpr/base-image:2.0
LABEL maintainer="faisal.ajmal@gmail.com"

ADD ./ocr /openlpr/ocr
WORKDIR /openlpr/ocr

ENTRYPOINT [ "python3","/openlpr/ocr/ocr.py"]