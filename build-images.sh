#!/bin/sh
rm -f ./ftp/ftp.service.log
rm -f ./platedetector/platedetector.service.log
rm -f ./plateclassifier/plateclassifier.service.log
rm -f ./ocr/ocr.service.log

# build context paths are important
docker build -t openlpr/base-image:2.0 -f ./docker/lpr-base-img/Dockerfile .
docker build -t openlpr/nodered:v10 -f ./docker/nodered/Dockerfile ./docker/nodered 
docker build -t openlpr/ftp:2.0 -f ./docker/ftp/Dockerfile .
docker build -t openlpr/platedetector:2.0 -f ./docker/platedetector/Dockerfile .
docker build -t openlpr/plateclassifier:2.0 -f ./docker/plateclassifier/Dockerfile .
docker build -t openlpr/ocr:2.0 -f ./docker/ocr/Dockerfile .
