FROM python:3
LABEL maintainer="faisal.ajmal@gmail.com"

ADD ./shared /openlpr/shared
ADD ./plateclassifier /openlpr/plateclassifier
ADD ./shared/empty /filestorage/
ADD ./shared/empty /models/

WORKDIR /openlpr/plateclassifier

RUN pip3 install --no-cache-dir -r /openlpr/shared/requirements.txt && \
    pip3 install --no-cache-dir -r /openlpr/plateclassifier/requirements.txt

ENTRYPOINT [ "python3","/openlpr/plateclassifier/plateclassifier.py"]