FROM python:3.8
LABEL maintainer="faisal.ajmal@gmail.com"

ADD ./shared /openlpr/shared
ADD ./shared/empty /filestorage/
ADD ./shared/empty /models/

RUN sh -c "/openlpr/shared/install-python-deps.sh"