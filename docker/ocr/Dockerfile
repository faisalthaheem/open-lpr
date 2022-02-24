FROM python:3.8.12-slim
LABEL maintainer="faisal.ajmal@gmail.com"


RUN DEBIAN_FRONTEND=noninteractive apt update && \
    DEBIAN_FRONTEND=noninteractive apt install -y wget curl unzip && \
    mkdir -p /filestorage && \
    mkdir -p /openlpr/ && \
    mkdir -p /root/.EasyOCR/model

RUN wget -O /root/.EasyOCR/model/english_g2.zip 'https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/english_g2.zip' && \
    unzip -d /root/.EasyOCR/model /root/.EasyOCR/model/english_g2.zip && rm /root/.EasyOCR/model/english_g2.zip

RUN pip3 install --no-cache-dir \
    Events==0.4 \
    pymongo==4.0.1 \
    PyYAML==6.0 \
    pika \
    torch==1.10.2+cpu torchvision==0.11.3+cpu -f https://download.pytorch.org/whl/cpu/torch_stable.html \
    easyocr

#fix seg fault issue wiht easyocr and headless opencv
RUN pip3 uninstall -y opencv-python-headless && pip3 install opencv-python-headless==4.5.4.60

ADD ./ocr /openlpr/
WORKDIR /openlpr/

CMD [ "python3","/openlpr/ocr.py"]