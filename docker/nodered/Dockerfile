FROM nodered/node-red:2.2.2-14

RUN npm install --no-cache --save \
    @meowwolf/node-red-contrib-amqp \
    @ekaralis/node-red-contrib-sse-plus \
    node-red-contrib-mongodb3 \
    node-red-node-base64

ADD ["flows.json","settings.js","/data/"]
