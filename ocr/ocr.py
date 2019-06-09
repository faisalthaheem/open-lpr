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
    __package__ = "ocr"
    
from shared.amqp import ThreadedAmqp
import shared.utils as utils
import shared.cvfuncs as cvfuncs
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
        
        def __init__(self, args):
                
                self.lc_model, self.lc_classes, self.lc_graph, self.lc_sess = utils.loadModel(config['model']["modelfile"], config["model"]['modelLoss'])
        
     
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

        def classifyTextRois(self, rects, rois):

                letters = []
                filteredRects = []
                confidences = []
                
                try:
                        rois = rois / 255

                        with self.lc_graph.as_default():
                                with self.lc_sess.as_default():
                                        predictions = self.lc_model.predict(rois, 1)

                        for i in range(0,len(rois)):
                                max_score_i = np.argmax(predictions[i])
                                conf_i = predictions[i][max_score_i]
                                class_i = self.lc_classes[max_score_i]

                                if class_i != 'skipped' and conf_i >= 0.9:
                                        letters.append(class_i)
                                        filteredRects.append([
                                                float(rects[i][0]), #x
                                                float(rects[i][1]), #y
                                                float(rects[i][2]), #w
                                                float(rects[i][3]), #h
                                        ])
                                        confidences.append(float(conf_i))

                        return np.mean(confidences), filteredRects, confidences,''.join(letters[:6])
                except:
                        logger.error(traceback.format_exc())
                                
                return 0.0, [], [], ''


        def newImageQueued(self, msg):
                logger.debug(msg)

                try:
                        # load image
                        msg = json.loads(msg)

                        msg['ocr'] = []

                        # loop and ocr
                        for i in range(0, len(msg['plate_imgs'])):
                                if msg['classifications'][i]['score'] >= config['classification']['minScore']:
                                        
                                        plate_img = utils.load_image_into_numpy_array(msg['plate_imgs'][i], None, False)
                                        plate_class = msg['classifications'][i]['platetype']


                                        #extract text roi region
                                        text_roi_region = utils.extractTextRoiFromPlate(plate_img, plate_class)

                                        #find letter rois
                                        rects, rois = utils.find_rois(text_roi_region, True)

                                        #classify the letter rois
                                        avgTextConf, filteredRects, letterconfidences, lprtext = self.classifyTextRois(rects, rois)
                                        
                                else:
                                        avgTextConf, filteredRects, letterconfidences, lprtext  = 0.0, [], [], 'not classified'

                                msg['ocr'].append(
                                        {
                                                'avgTextConf': avgTextConf,
                                                'filteredRects': filteredRects,
                                                'letterconfidences': letterconfidences,
                                                'lprtext': lprtext
                                        }
                                )
                                logger.info("[{}] ocr [{}] with confidence [{}]".format(msg['_id'],lprtext, avgTextConf))

                        # save to db
                        self.updateDb(msg)

                        # dispatch to mq
                        self._publisher.publish_message(msg)

                except:
                        logger.error(sys.exc_info())


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

        ap.add_argument("-cf", "--config.file", default='ocr.yaml',
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


        detector = PlateClassifier(args)
        detector.loop_forever()


