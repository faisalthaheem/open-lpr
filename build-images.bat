del ./ftp/ftp.service.log
del ./platedetector/platedetector.service.log
del ./plateclassifier/plateclassifier.service.log
del ./ocr/ocr.service.log

rem build context paths are important
docker build -t openlpr/base-image:2.0 -f ./docker/lpr-base-img/Dockerfile .
docker build -t openlpr/nodered:v10 -f ./docker/nodered/Dockerfile ./docker/nodered 
docker build -t openlpr/ftp:2.0 -f ./docker/ftp/Dockerfile .
docker build -t openlpr/platedetector:2.0 -f ./docker/platedetector/Dockerfile .
docker build -t openlpr/plateclassifier:2.0 -f ./docker/plateclassifier/Dockerfile .
docker build -t openlpr/ocr:2.0 -f ./docker/ocr/Dockerfile .
