# Milestones

## Work on classification module is in progress.

![Milestones](https://rawcdn.githack.com/faisalthaheem/open-lpr/0bf07f8c06ce40fe42ff82e0e021d269225afde9/docs/Milestones.png)


# Overview

![Overview](https://rawcdn.githack.com/faisalthaheem/open-lpr/0451b44de1a7c2893236b9bafef7dcbc0f3bc79f/docs/overview.png)


Open LPR is a distributed system aimed towards ease of management and high lpr throughput. The core consists of modules to perform basic tasks such as detection and ocr on license plates and Node Red is used configure the "intelligence" or the business aspects thereby keeping the code changes to a minimum.

The entire stack is built on top of docker containers and is available in cpu only and gpu supported runtimes.

Tensorflow, Keras and OpenCV are used amongst other libraries to deliver the service. 