FROM python:3
LABEL maintainer="faisal.ajmal@gmail.com"

ADD ./shared /openlpr/shared
ADD ./ocr /openlpr/ocr
ADD ./shared/empty /filestorage/
ADD ./shared/empty /models/

WORKDIR /openlpr/ocr

RUN pip3 install --no-cache-dir -r /openlpr/shared/requirements.txt && \
    pip3 install --no-cache-dir -r /openlpr/ocr/requirements.txt

ENTRYPOINT [ "python3","/openlpr/ocr/ocr.py"]