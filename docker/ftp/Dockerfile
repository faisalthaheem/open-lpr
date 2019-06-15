FROM python:3
LABEL maintainer="faisal.ajmal@gmail.com"

ADD ./shared /openlpr/shared
ADD ./ftp /openlpr/ftp
ADD ./shared/empty /filestorage/
ADD ./shared/empty /temp-storage/

WORKDIR /openlpr/ftp

RUN pip3 install --no-cache-dir -r /openlpr/shared/requirements.txt && \
    pip3 install --no-cache-dir -r /openlpr/ftp/requirements.txt

EXPOSE 2121

ENTRYPOINT [ "python3","/openlpr/ftp/ftp.service.py"]