FROM nodered/node-red-docker:v10

RUN npm install --save \
    node-red-contrib-amqp \
    @ekaralis/node-red-contrib-sse-plus \
    node-red-contrib-image-tools  \
    node-red-node-mongodb \
    node-red-contrib-mongodb

ADD flows.json /data