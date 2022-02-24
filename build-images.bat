
rem build context paths are important
docker build -t openlpr/nodered:2.2.2-14 -f ./docker/nodered/Dockerfile ./docker/nodered 
docker build -t openlpr/ftp:3.0 -f ./docker/ftp/Dockerfile .
docker build -t openlpr/platedetector:3.0 -f ./docker/platedetector/Dockerfile .
docker build -t openlpr/ocr:3.0 -f ./docker/ocr/Dockerfile .
