"""
   Copyright 2019 Faisal Thaheem

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

from amqp import ThreadedAmqp

import pprint
import yaml
import os
import argparse as argparse
import json
import logging
import signal
from pymongo import MongoClient
import easyocr
import cv2

#create logger
logger = logging.getLogger('ocr.service')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('ocr.service.log')
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# create formatter and add it to the handlers
formatter = logging.Formatter('[%(levelname)1.1s %(asctime)s] %(message)s',"%Y-%m-%d %H:%M:%S")
fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)


class PlateClassifier():
        lc_model, lc_classes, lc_graph, lc_sess = None,None,None,None
        _consumer = None
        _publisher = None
        reader = None
        
        def __init__(self, args):
                
                self.reader = easyocr.Reader(['en'],gpu=False)
     
                brokerUrl = config['broker']['uri']
                logger.info("Using broker url [{}]".format(brokerUrl))

                self._consumer = ThreadedAmqp()
                self._consumer.callbackEvents.on_message += self.newImageQueued
                self._consumer.init(
                        brokerUrl,
                        consumerMode=True,
                        exchange=config['broker']['consumeFrom']['exchange'],
                        exchangeType=config['broker']['consumeFrom']['exchangeType'],
                        routingKey=config['broker']['consumeFrom']['routingKey'],
                        queueName=config['broker']['consumeFrom']['queueName'],
                )
                
                self._publisher = ThreadedAmqp()
                self._publisher.init(
                        brokerUrl,
                        exchange=config['broker']['publishTo']['exchange'],
                        exchangeType=config['broker']['publishTo']['exchangeType'],
                        routingKey=config['broker']['publishTo']['routingKey'],
                        consumerMode=False
                )
 
                logger.info("Init complete")

        def cleanup(self):
                if self._consumer is not None:
                        self._consumer.stop()

                if self._publisher is not None:
                        self._publisher.stop()

        def loop_forever(self):
                self._consumer.start()
                self._publisher.start()


        def getDbConnection(self):
                
                client = MongoClient(config['mongo']['uri'])

                #open db
                if not "openlpr" in client.list_database_names():
                        logger.info("database openlpr does not exist, will be created after first document insert")
                        
                return client

        def getDoc(self, docid):

                client = self.getDbConnection()

                db = client["openlpr"]
                query = {"_id": docid}

                col = db['lprevents']
                document = col.find_one(query)

                client.close()
                
                return document
                
        def updateDb(self, doc):

                client = self.getDbConnection()

                db = client["openlpr"]
                query = {"_id": doc['_id']}
                updatedDoc = { "$set": doc}

                col = db['lprevents']
                col.update_one(query, updatedDoc)

                client.close()

        
        def newImageQueued(self, msg):

                try:
                        # load image
                        msg = json.loads(msg)

                        msg['ocr'] = []
                        
                        # loop and perform ocr on image regions identified as plates
                        for i in range(0, len(msg['detections']['boxes'])):
                                if msg['detections']['scores'][i] >= config['detection']['minScore']:
                                        
                                        diskpath = os.path.join(config['storage']['path'], msg['unique_name'])
                                        orig_img = cv2.imread(diskpath)

                                        #focus on the plate
                                        (x,y,w,h) = msg['detections']['boxes'][i]
                                        w = w-x
                                        h = h-y
                                        
                                        plate_img= orig_img[y:y+h, x:x+w]

                                        #find letter rois
                                        ocr_raw = self.reader.readtext(plate_img)
                                        
                                        for (regions, text, conf) in ocr_raw:
                                                logger.debug("Evaluating ocr result [Text: {}, Conf: {}]".format(text, conf))
                                                
                                                if conf >= config['ocr']['minScore']:
                                                        msg['ocr'].append(
                                                                [
                                                                        text,
                                                                        float(conf)
                                                                ]
                                                        )

                                                        logger.debug("Accepted [{}]".format(text))
                                                else:
                                                        logger.debug("Ignored [{}] due to low confidence".format(text))
                
                        # save to db
                        self.updateDb(msg)

                        # dispatch to mq
                        self._publisher.publish_message(msg)

                except:
                        logger.error("An error occurred: ", exc_info=True)


def signal_handler(sig, frame):
    try:
        logger.info("Ctrl-c pressed, stopping")
        
        if detector is not None:
                detector.cleanup()
    except:
        logger.error("An error occurred: ", exc_info=True)
    

if __name__ == '__main__':

        global args
        global config
        global detector

        ap = argparse.ArgumentParser()

        ap.add_argument("-cf", "--config.file", default='ocr.yaml',
                help="Config file describing service parameters")

        args = vars(ap.parse_args())

        #handle ctrl-c
        signal.signal(signal.SIGINT, signal_handler)

        with open(args["config.file"]) as stream:
                try:
                        if os.getenv('PRODUCTION') is not None: 
                                config = yaml.safe_load(stream)['prod']
                        else:
                                config = yaml.safe_load(stream)['dev']

                        pprint.pprint(config)

                except yaml.YAMLError as err:
                        logger.error("An error occurred: ", exc_info=True)


        detector = PlateClassifier(args)
        detector.loop_forever()


