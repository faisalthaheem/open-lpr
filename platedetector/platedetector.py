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

# Ugly hack to allow absolute import from the root folder
# whatever its name is. Please forgive the heresy.
if __name__ == "__main__" and __package__ is None:
    from sys import path
    from os.path import dirname as dir

    path.append(dir(path[0]))
    __package__ = "platedetector"
    
from shared.amqp import ThreadedAmqp
import shared.utils as utils
from shared.obj_detector import ObjDetector

import pprint
import yaml
import threading
import sys
import numpy as np
import time
import os
import argparse as argparse
import json
import queue
import uuid
import logging
import pickle
import traceback
import signal
import json
from pymongo import MongoClient
from skimage.transform import resize


#create logger
logger = logging.getLogger('platedetector.service')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('platedetector.service.log')
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


class PlateDetector():
        platedetector = None
        _consumer = None
        _publisher = None
        
        def __init__(self, args):
                
                self.platedetector = ObjDetector()
                self.platedetector.init(
                        args["model.path"],
                        args["label.path"])

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

        def updateDb(self, doc):

                client = MongoClient(config['mongo']['uri'])

                #open db
                if not "openlpr" in client.database_names():
                        logger.info("database openlpr does not exist, will be created after first document insert")
                        
                db = client["openlpr"]
                query = {"_id": doc['_id']}
                updatedDoc = { "$set": doc}

                col = db['lprevents']
                col.update_one(query, updatedDoc)

                client.close()

        def newImageQueued(self, msg):
                logger.debug(msg)

                try:
                        # load image
                        msg = json.loads(msg)

                        diskpath = os.path.join(config['storage']['path'], msg['unique_name'])
                        originalImage = utils.load_image_into_numpy_array(diskpath, None, False)
                        originalShape = originalImage.shape
                        originalImage = None

                        msg['imgDimensions'] = {
                                "height": originalShape[0],
                                "width": originalShape[1],
                                "channels": originalShape[2]
                        }
                        
                        img = utils.load_image_into_numpy_array(
                                diskpath, 
                                (config['detection']['loadHeight'],config['detection']['loadWidth']), 
                                config['detection']['grayScale'])

                        logger.debug("Loaded image [{}]".format(diskpath))

                        # detect plates
                        detections = self.detectPlate(img, originalShape)
                        logger.debug(detections)

                        # save to db
                        msg['detections'] = detections
                        self.updateDb(msg)

                        # dispatch to mq
                        self._publisher.publish_message(msg)

                except:
                        logger.error(sys.exc_info())

        def detectPlate(self, imgData, originalShape):

                start=time.time()
                
                h,w,_ = imgData.shape
                oh,ow,_ = originalShape
                mulH = oh/h
                mulW = ow/w
                
                image_np_expanded = np.expand_dims(imgData, axis=0)
                (boxes, scores, classes, num) = self.platedetector.detect(image_np_expanded)
                end=time.time()
                
                translatedBoxes = []
                for box in boxes[0]:
                        translatedBoxes.append(
                                (
                                int(box[0] * h * mulH),
                                int(box[1] * w * mulW),
                                int(box[2] * h * mulH),
                                int(box[3] * w * mulW),
                                )
                        )
                
                return {
                        'boxes': translatedBoxes[:10],
                        'scores': scores[0].tolist()[:10],
                        'classes': classes[0].tolist()[:10]
                }

def signal_handler(sig, frame):
    try:
        logger.info("Ctrl-c pressed, stopping")
        
        if detector is not None:
                detector.cleanup()
    except:
        logger.error(sys.exc_info())
    

if __name__ == '__main__':

        global args
        global config
        global detector

        ap = argparse.ArgumentParser()

        ap.add_argument("-mp", "--model.path", required=True,
                help="folder containing the model")
        ap.add_argument("-lp", "--label.path", required=True,
                help="path to labels")

        ap.add_argument("-cf", "--config.file", default='platedetector.yaml',
                help="Config file describing service parameters")

        args = vars(ap.parse_args())

        #handle ctrl-c
        signal.signal(signal.SIGINT, signal_handler)

        with open(args["config.file"]) as stream:
                try:
                        if os.getenv('PRODUCTION') is not None: 
                                config = yaml.load(stream)['prod']
                        else:
                                config = yaml.load(stream)['dev']

                        pprint.pprint(config)
                except yaml.YAMLError as err:
                        logger.error(err)


        detector = PlateDetector(args)
        detector.loop_forever()


