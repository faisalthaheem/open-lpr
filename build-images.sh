#!/bin/sh
# build context paths are important
# docker build -t openlpr/nodered:v10 -f ./docker/nodered/Dockerfile ./docker/nodered 
# docker build -t openlpr/ftp:1.0 -f ./docker/ftp/Dockerfile .
docker build -t openlpr/platedetector:1.0 -f ./docker/platedetector/Dockerfile .
