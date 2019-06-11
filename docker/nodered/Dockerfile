FROM nodered/node-red-docker:v10

RUN npm install --save \
    node-red-contrib-amqp \
    node-red-contrib-sse-plus \
    node-red-contrib-image-tools  

ADD flows.json /data