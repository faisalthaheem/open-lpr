FROM openlpr/base-image:2.0
LABEL maintainer="faisal.ajmal@gmail.com"

ADD ./ftp /openlpr/ftp
ADD ./shared/empty /temp-storage/
WORKDIR /openlpr/ftp

EXPOSE 2121

ENTRYPOINT [ "python3","/openlpr/ftp/ftp.service.py"]