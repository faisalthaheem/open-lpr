FROM python:3
LABEL maintainer="faisal.ajmal@gmail.com"

WORKDIR /openlpr/ftp
ADD ./ftp /openlpr/ftp

WORKDIR /openlpr/shared
ADD ./shared /openlpr/shared

ADD ./shared/empty /filestorage/

RUN pip3 install --no-cache-dir -r /openlpr/shared/requirements.txt && \
    pip3 install --no-cache-dir -r /openlpr/ftp/requirements.txt

EXPOSE 2121

ENTRYPOINT [ "python3","/openlpr/ftp/ftp.service.py"]