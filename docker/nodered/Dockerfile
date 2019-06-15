FROM nodered/node-red-docker:v10

RUN npm install --no-cache --save \
    node-red-contrib-amqp \
    @ekaralis/node-red-contrib-sse-plus \
    node-red-contrib-image-tools  \
    node-red-contrib-mongodb3 

ADD ["flows.json","settings.js","/data/"]