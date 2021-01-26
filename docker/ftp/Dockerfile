FROM python:3.8
LABEL maintainer="faisal.ajmal@gmail.com"

ADD ./shared /openlpr/shared
ADD ./ftp /openlpr/ftp
ADD ./shared/empty /filestorage/
ADD ./shared/empty /temp-storage/

WORKDIR /openlpr/ftp

RUN sh -c "/openlpr/shared/install-python-deps.sh" && \
    pip3 install --no-cache-dir -r /openlpr/ftp/requirements.txt

EXPOSE 2121

ENTRYPOINT [ "python3","/openlpr/ftp/ftp.service.py"]