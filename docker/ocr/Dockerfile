FROM python:3.8
LABEL maintainer="faisal.ajmal@gmail.com"

ADD ./shared /openlpr/shared
ADD ./ocr /openlpr/ocr
ADD ./shared/empty /filestorage/
ADD ./shared/empty /models/

WORKDIR /openlpr/ocr

RUN sh -c "/openlpr/shared/install-python-deps.sh" && \
    pip3 install --no-cache-dir -r /openlpr/ocr/requirements.txt

ENTRYPOINT [ "python3","/openlpr/ocr/ocr.py"]