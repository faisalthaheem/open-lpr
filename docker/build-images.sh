#!/bin/sh

docker build -t openlpr/nodered:v10 -f nodered/Dockerfile ./nodered 
docker build -t openlpr/pythondev:v3.7 -f python3dev/Dockerfile ./python3dev
