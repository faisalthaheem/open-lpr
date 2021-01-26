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

if __name__ == "__main__" and __package__ is None:
    from sys import path
    from os.path import dirname as dir

    path.append(dir(path[0]))
    __package__ = "plateclassifier"
    
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
import cv2


#create logger
logger = logging.getLogger('plateclassifier.service')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('plateclassifier.service.log')
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
        pc_model, pc_classes, pc_graph, pc_sess = None,None,None,None
        _consumer = None
        _publisher = None
        
        def __init__(self, args):
                
                self.pc_model, self.pc_classes, self.pc_graph, self.pc_sess = utils.loadModel(config['model']["modelfile"], config["model"]['modelLoss'])
        
     
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

        def classifyPlate(self, img):

                plate_img_with_black_bg = utils.overlayImageOnBlackCanvas(img)
                plate_img_gs = utils.convertToGrayscaleForClassification(plate_img_with_black_bg)
                plate_img_expanded = np.expand_dims(plate_img_gs, axis=0)
                
                with self.pc_graph.as_default():
                        with self.pc_sess.as_default():
                                predictions = self.pc_model.predict(plate_img_expanded)

                max_score_index = np.argmax(predictions[0])

                return self.pc_classes[max_score_index], float(predictions[0][max_score_index])

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
                if not "openlpr" in client.database_names():
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
                logger.debug(msg)

                try:
                        # load image
                        msg = json.loads(msg)

                        diskpath = os.path.join(config['storage']['path'], msg['unique_name'])
                        originalImage = utils.load_image_into_numpy_array(diskpath, None, False)
                        originalShape = originalImage.shape
                        
                        logger.debug("Loaded image [{}]".format(diskpath))

                        msg['classifications'] = []
                        document = msg

                        # slice
                        plate_images = []
                        for i in range(0, len(document['detections']['boxes'])):
                                if document['detections']['scores'][i] >= config['classification']['minScore']:
                                        plateImage = originalImage[
                                                document['detections']['boxes'][0][0]:document['detections']['boxes'][0][2],
                                                document['detections']['boxes'][0][1]:document['detections']['boxes'][0][3]
                                        ]

                                        #save this plate image to be used in ocr
                                        filename = "{}_plate_{}.jpg".format(msg['_id'],i)
                                        plate_images.append(filename)

                                        filename = os.path.join(config['storage']['path'], filename)

                                        cv2.imwrite(filename, cv2.cvtColor(plateImage.copy(), cv2.COLOR_RGB2BGR))

                                        platetype, score  = self.classifyPlate(plateImage)
                                        
                                else:
                                        platetype, score  = 'not classified',0.0


                                msg['classifications'].append(
                                        {
                                                'platetype': platetype,
                                                'score': score
                                        }
                                )
                                logger.info("[{}] classified as [{}] with confidence [{}]".format(msg['_id'],platetype, score))

                        #todo fix later, possible bug, num plates inequal num classifications/detections
                        msg['plate_imgs'] = plate_images
                        
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

        ap.add_argument("-cf", "--config.file", default='plateclassifier.yaml',
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
                        logger.error("An error occurred: ", exc_info=True)


        detector = PlateClassifier(args)
        detector.loop_forever()


