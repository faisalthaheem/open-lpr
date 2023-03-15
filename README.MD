|Repository|Last commit|Docker CI Health|Docker pulls|
|---|---|---|---|
|[FTP](https://github.com/faisalthaheem/open-lpr-ftp)|![GithubLastCommit](https://img.shields.io/github/last-commit/faisalthaheem/open-lpr-ftp)|[![Docker Image CI](https://github.com/faisalthaheem/open-lpr-ftp/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/faisalthaheem/open-lpr-ftp/actions/workflows/docker-publish.yml)|![DockerPulls](https://img.shields.io/docker/pulls/faisalthaheem/open-lpr-ftp)|
|[Plate Detection](https://github.com/faisalthaheem/open-lpr-plate-detection)|![GithubLastCommit](https://img.shields.io/github/last-commit/faisalthaheem/open-lpr-plate-detection)|[![Docker Image CI](https://github.com/faisalthaheem/open-lpr-plate-detection/actions/workflows/docker-image.yml/badge.svg)](https://github.com/faisalthaheem/open-lpr-plate-detection/actions/workflows/docker-image.yml)|![DockerPulls](https://img.shields.io/docker/pulls/faisalthaheem/open-lpr-plate-detection)|
|[OCR](https://github.com/faisalthaheem/open-lpr-ocr)|![GithubLastCommit](https://img.shields.io/github/last-commit/faisalthaheem/open-lpr-ocr)|[![Docker Image CI](https://github.com/faisalthaheem/open-lpr-ocr/actions/workflows/docker-image.yml/badge.svg)](https://github.com/faisalthaheem/open-lpr-ocr/actions/workflows/docker-image.yml)|![DockerPulls](https://img.shields.io/docker/pulls/faisalthaheem/open-lpr-ocr)|
|[REST](https://github.com/faisalthaheem/open-lpr-rest)|![GithubLastCommit](https://img.shields.io/github/last-commit/faisalthaheem/open-lpr-rest)|[![Docker Image CI](https://github.com/faisalthaheem/open-lpr-rest/actions/workflows/docker-image.yml/badge.svg)](https://github.com/faisalthaheem/open-lpr-rest/actions/workflows/docker-image.yml)|![DockerPulls](https://img.shields.io/docker/pulls/faisalthaheem/open-lpr-rest)|
|[NodeRed](https://github.com/faisalthaheem/open-lpr-nodered)|![GithubLastCommit](https://img.shields.io/github/last-commit/faisalthaheem/open-lpr-nodered)|[![Docker Image CI](https://github.com/faisalthaheem/open-lpr-nodered/actions/workflows/docker-image.yml/badge.svg)](https://github.com/faisalthaheem/open-lpr-nodered/actions/workflows/docker-image.yml)|![DockerPulls](https://img.shields.io/docker/pulls/faisalthaheem/open-lpr-nodered)|

<br/>

# TOC
- [Demo](https://github.com/faisalthaheem/open-lpr#demo)
- [About](https://github.com/faisalthaheem/open-lpr#about)
- [Quick Start in 3 steps](https://github.com/faisalthaheem/open-lpr#quick-start-in-3-steps)
- [REST interface](https://github.com/faisalthaheem/open-lpr#rest-interface)
- [Training your own Plate Detection Models](https://github.com/faisalthaheem/open-lpr#training-your-own-plate-detection-models)
- [Milestones](https://github.com/faisalthaheem/open-lpr#milestones)
- [Overview](https://github.com/faisalthaheem/open-lpr#overview)

# Demo
## [Visit here for a live demo of REST interface](https://rest-openlpr.computedsynergy.com/). 
Please note the demo server is deliberately kept underpowered to prevent abuse. In case your request times out the server may just be too busy with other requests. You can always try running OpenLPR locally as described below.

<br/>

# About

> **Free forever & Open Source License Plate Recognition software which uses deep neural networks to detect license plates and perform OCR.**

Following image illustrates a dashboard built using nodered that shows real time LPR results. NodeRED can be used to build RESTful services, integrate with other systems such as over modbus to extend the business functionality of the system with ease.

![In Action | LPR Performed on an image and results displayed in NodeRED Dashboard](docs/jeep-lpr.png?raw=true)

In the above example it can be see that LPR was performed on the image uploaded through FTP and text 349253 was extracted successfully from the license plate area.

An abundance of information such as bounding boxes, confidence scores etc are available in the raw JSON data published by the services and available to NodeRED and any other integrating service for consumption.
 
 For the above example, the following detail is available in db and also published on the message broker (RabbitMQ) and is as well available in NodeRED for further processing, furthermore this detail is also returned as JSON when using the REST (described further below) interface

```json
{
    "_id" : "522676bf-c958-49cb-b786-32b3d0407c02",
    "filename" : "jeep.jpg",
    "creationtime" : 1645719472.51666,
    "unique_name" : "522676bf-c958-49cb-b786-32b3d0407c02_jeep.jpg",
    "detections" : {
        "boxes" : [ 
            [ 
                348, 
                400, 
                740, 
                546
            ]
        ],
        "scores" : [ 
            0.998433649539948
        ],
        "classes" : [ 
            2
        ]
    },
    "imgDimensions" : {
        "height" : 1281,
        "width" : 720,
        "channels" : "RGB"
    },
    "ocr" : [ 
        [ 
            "349253", 
            0.996076437906518
        ]
    ]
}
```

<br/><br/>

# Quick Start in 3 steps

The following instrctions assume you are running a linux flavor such as debian, ubuntu or popos!

## 1. Install [Docker](https://www.docker.com/get-started)
Goto https://www.docker.com/get-started and install the distribution relevant to your operating system. Consider using a convenience script to fast track the installation.
Also install docker-compose.

## 2. Clone this repo & start services
This step will take a few minutes depending on your internet connection speed. Use "bash" shell to issue the following commands

```bash
git clone https://github.com/faisalthaheem/open-lpr && \
cd open-lpr && \
docker-compose up -d
```
> **Important** Images are updated frequently, therefore to ensure you are running the latest version consider using watchtower.
## 3. Open your browser and upload file to process

Use google chrome to navigate to the following address
http://localhost:5000/

## Optional - Upload a file using FTP

Use any FTP client, for example, [FileZilla](https://filezilla-project.org/) to connect to your localhost on port 2121 with the username and password user/12345 and upload any car image with readable license plate.

The dashboard at http://localhost:1890/show-dashboard will update to reflect the detected plate and OCR text like in the image above.

<br/><br/>

# REST Interface

You can use the REST interface to submit an image for processing. Once services have started a command similar to following can be used from the shell to try it out; you can ofcourse use the REST interface with any programming language.

```bash
curl \
  -F "filecomment=Sample file" \
  -F "image=@/path/to/image.jpg" \
  localhost:5000/process
```

In the above command `image==@/path/to/image.jpg` points to the file that is to be submitted for processing, and localhost:5000 represents where the OpenLPR services are running.

The returned response is JSON as given in the example above

<br/><br/>

# Training your own Plate Detection Models
Please follow instructions given in the following repo
[OpenLPR Pre-trained models](https://github.com/faisalthaheem/open-lpr-pretrained-models)

<br/><br/>

# Documentation & Updates
Head over to the wiki for [documentation](https://github.com/faisalthaheem/open-lpr/wiki/Documentation).

Dated|Description
---|---
Feb 2022|Added arm64 support to all containers except OCR and detection.
Feb 2022|Added REST interface.
Feb 2022|Ported stack to torch. Removed plate classification.
Feb 2022|Completed documentation.
Jan 2021|Ported to tensorflow 2 with compatibility mode for tensorflow 1.

<br/><br/>

# Milestones


## Work on GPU supported container images is in progress.

![Milestones](https://raw.githack.com/faisalthaheem/open-lpr/master/docs/Milestones.png)


<br/><br/>

# Overview

Open LPR is a distributed system aimed towards ease of management and high LPR throughput. The core consists of modules to perform the tasks of plate detection, classification and OCR.

Ground up the system is built to be scalable and can handle the load of a single site to a city wide area.

The entire stack is built on top of docker containers and is available in cpu only and gpu supported runtimes.
Tensorflow, Keras and OpenCV are used amongst other libraries to deliver the service.

![Overview](https://rawcdn.githack.com/faisalthaheem/open-lpr/b701dd0df6278ee4209c5671af3b345d096bfe62/docs/overview-v2.png)
