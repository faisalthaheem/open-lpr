FROM python:3.8
LABEL maintainer="faisal.ajmal@gmail.com"

ADD ./shared /openlpr/shared
ADD ./plateclassifier /openlpr/plateclassifier
ADD ./shared/empty /filestorage/
ADD ./shared/empty /models/

WORKDIR /openlpr/plateclassifier

RUN sh -c "/openlpr/shared/install-python-deps.sh" && \
    pip3 install --no-cache-dir -r /openlpr/plateclassifier/requirements.txt

ENTRYPOINT [ "python3","/openlpr/plateclassifier/plateclassifier.py"]