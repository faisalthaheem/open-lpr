
# Open LPR
**Free forever Open Source License Plate Recognition software which uses deep neural networks to detect license plates, classify them and perform OCR.**

Following image illustrates a dashboard built using nodered that shows real time LPR results. NodeRED can be used to build RESTful services, integrate with other systems such as over modbus to extend the business functionality of the system.


![In Action](https://rawcdn.githack.com/faisalthaheem/open-lpr/f60aa4c7a48470d278d814804e3d53eb6f01318a/docs/alpr-result.jpg)
Shows 349253 as the license plate text, and qa.priv_broad as the type of number plate. An abundance of information such as bounding boxes, confidence scores etc are availabel in the raw JSON data published by the services and available to NodeRED and any other integrating service for consumption.
# Documentation & Updates
Head over to the wiki for [documentation](https://github.com/faisalthaheem/open-lpr/wiki/Documentation).

**Jan 13, 2021**: Ported to tensorflow 2 with compatibility mode for tensorflow 1.



# Quick Start

 1. Install [Docker](https://www.docker.com/get-started) 
 2. Open shell and issue build-images.sh or build-images.bat and wait for the process to complete
 3. While on shell issue docker-compose up -d and wait for services to start 
 4. Open browser and navigate to [dashboard](http://localhost:1890/show-dashboard)
 5. Using any FTP software (or configure your camera) connect to localhost port 2121 with username "user" and password "12345" (without quotes) and upload upto a Full-HD image

The dashboard will update to reflect the detected plate and OCR text like in the image above

 
# Milestones

  

## Work on Documentation is in progress.

  

![Milestones](https://raw.githack.com/faisalthaheem/open-lpr/master/docs/Milestones.png)

  
  

# Overview

Open LPR is a distributed system aimed towards ease of management and high LPR throughput. The core consists of modules to perform the tasks of plate detection, classification and OCR.

Ground up the system is built to be scalable and can handle the load of a single site to a city wide area.

The entire stack is built on top of docker containers and is available in cpu only and gpu supported runtimes.
Tensorflow, Keras and OpenCV are used amongst other libraries to deliver the service.

![Overview](https://rawcdn.githack.com/faisalthaheem/open-lpr/b701dd0df6278ee4209c5671af3b345d096bfe62/docs/overview-v2.png)
