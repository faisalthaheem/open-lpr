
# Open LPR

> **Free forever & Open Source License Plate Recognition software which uses deep neural networks to detect license plates and perform OCR.**

Following image illustrates a dashboard built using nodered that shows real time LPR results. NodeRED can be used to build RESTful services, integrate with other systems such as over modbus to extend the business functionality of the system with ease.

![In Action | LPR Performed on an image and results displayed in NodeRED Dashboard](docs/jeep-lpr.png?raw=true)

In the above example it can be see that LPR was performed on the image uploaded through FTP and text 349253 was extracted successfully from the license plate area.

 An abundance of information such as bounding boxes, confidence scores etc are available in the raw JSON data published by the services and available to NodeRED and any other integrating service for consumption.
 
 For the above example, the following detail is available in db and also published on the message broker (RabbitMQ) and is as well available in NodeRED for further processing

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

# Quick Start

The following instrctions assume you are running a linux flavor such as debian, ubuntu or popos!

 1. Install [Docker](https://www.docker.com/get-started) 
 2. Open shell and issue build-images.sh and wait for the process to finish.
 3. While on shell issue docker-compose up -d and wait for services to start 
 4. Open browser and navigate to [dashboard](http://localhost:1890/show-dashboard)
 5. Using any FTP client software (or configure your camera) to connect to localhost (or the ip of your pc) on port 2121 with username "user" and password "12345" (without quotes) and upload an image containing a car with a readable number plate.

The dashboard will update to reflect the detected plate and OCR text like in the image above.

# Training your own Plate Detection Models
Please follow instructions given in the following repo
[OpenLPR Pre-trained models](https://github.com/faisalthaheem/open-lpr-pretrained-models)

# Documentation & Updates
Head over to the wiki for [documentation](https://github.com/faisalthaheem/open-lpr/wiki/Documentation).

Dated|Description
---|---
Feb 2022|Ported stack to torch. Removed plate classification.
Feb 2022|Completed documentation.
Jan 2021|Ported to tensorflow 2 with compatibility mode for tensorflow 1.
 
# Milestones
 

## Work on Documentation is in progress.

![Milestones](https://raw.githack.com/faisalthaheem/open-lpr/master/docs/Milestones.png)
  

# Overview

Open LPR is a distributed system aimed towards ease of management and high LPR throughput. The core consists of modules to perform the tasks of plate detection, classification and OCR.

Ground up the system is built to be scalable and can handle the load of a single site to a city wide area.

The entire stack is built on top of docker containers and is available in cpu only and gpu supported runtimes.
Tensorflow, Keras and OpenCV are used amongst other libraries to deliver the service.

![Overview](https://rawcdn.githack.com/faisalthaheem/open-lpr/b701dd0df6278ee4209c5671af3b345d096bfe62/docs/overview-v2.png)
