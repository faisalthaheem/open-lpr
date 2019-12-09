FROM nodered/node-red-docker:0.18.7-v8

RUN npm install --no-cache --save \
    node-red-contrib-amqp@1.0.1 \
    @ekaralis/node-red-contrib-sse-plus \
    node-red-contrib-mongodb3 

ADD ["flows.json","settings.js","/data/"]
