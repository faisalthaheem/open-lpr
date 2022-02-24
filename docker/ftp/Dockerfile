FROM python:3.8.12-slim
LABEL maintainer="faisal.ajmal@gmail.com"


RUN pip3 install --no-cache-dir \
    Events==0.4 \
    pika==1.2.0 \
    pyftpdlib==1.5.6 \
    pymongo==4.0.1 \
    PyYAML==6.0 && \
    mkdir -p /temp-storage/ && \
    mkdir -p /filestorage

WORKDIR /openlpr

ADD ["./ftp/","/openlpr"]

EXPOSE 2121 60000-60050

CMD [ "python3","/openlpr/ftp.service.py"]