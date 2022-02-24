FROM python:3.8.12-slim
LABEL maintainer="faisal.ajmal@gmail.com"


RUN DEBIAN_FRONTEND=noninteractive apt update && \
    DEBIAN_FRONTEND=noninteractive apt install -y wget curl && \
    mkdir -p /filestorage/ && \
    mkdir -p /openlpr/ && \
    mkdir -p /root/.cache/torch/hub/checkpoints/

RUN wget -O /openlpr/ssd.pth 'https://api.onedrive.com/v1.0/shares/s!AvNYo0I9EXbwh1mFaEqZNmUjQs99/root/content' && \
    wget -O /root/.cache/torch/hub/checkpoints/resnet50-0676ba61.pth 'https://download.pytorch.org/models/resnet50-0676ba61.pth'

RUN pip3 install --no-cache-dir \
    Events==0.4 \
    pymongo==4.0.1 \
    PyYAML==6.0 \
    pika \
    torch==1.10.2+cpu torchvision==0.11.3+cpu torchaudio==0.10.2+cpu -f https://download.pytorch.org/whl/cpu/torch_stable.html

WORKDIR /openlpr

ADD ./platedetector /openlpr

CMD [ "python3","/openlpr/platedetector.py", "--model", "/openlpr/ssd.pth"]