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

import numpy as np
import argparse
import torch
from transform import SSDTransformer
from PIL import Image

from utils import generate_dboxes, Encoder, colors, coco_classes
from model import SSD, ResNet

from utilsopenlpr import open_lpr_classes

import pprint
import yaml
import numpy as np
import os
import argparse as argparse
import json
import logging
import signal
import json
from pymongo import MongoClient


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

        _consumer = None
        _publisher = None
        
        def __init__(self, args):
                print(args)
                self.model = SSD(backbone=ResNet())
                
                if torch.cuda.is_available():
                        checkpoint = torch.load(args['model'])
                else:
                        map_location=torch.device('cpu')
                        checkpoint = torch.load(args['model'], map_location=map_location)
                        
                self.model.load_state_dict(checkpoint["model_state_dict"])
                if torch.cuda.is_available():
                        self.model.cuda()
                self.model.eval()
                dboxes = generate_dboxes()
                self.transformer = SSDTransformer(dboxes, (300, 300), val=True)
                self.encoder = Encoder(dboxes)

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
                print(doc)

                client = MongoClient(config['mongo']['uri'])

                #open db
                if not "openlpr" in client.list_database_names():
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
                        img = Image.open(diskpath).convert("RGB")
                        
                        width = img.width
                        height = img.height

                        msg['imgDimensions'] = {
                                "height": img.width,
                                "width": img.height,
                                "channels": img.mode
                        }

                        img, _, _, _ = self.transformer(img, None, torch.zeros(1,4), torch.zeros(1))
                        if torch.cuda.is_available():
                                img = img.cuda()

                        logger.debug("Loaded image [{}]".format(diskpath))


                        # detect plates
                        with torch.no_grad():
                                ploc, plabel = self.model(img.unsqueeze(dim=0))
                                result = self.encoder.decode_batch(ploc, plabel, args['nms_threshold'], 20)[0]
                                loc, label, prob = [r.cpu().numpy() for r in result]
                                best = np.argwhere(prob > args['cls_threshold']).squeeze(axis=1)
                                loc = loc[best]
                                label = label[best]
                                prob = prob[best]

                                
                                        
                                logger.debug(label)
                                logger.debug(loc)
                                logger.debug(prob)
                                
                                originalLocations = []
                                for l in loc:
                                        l[0] *= width
                                        l[2] *= width
                                        l[1] *= height
                                        l[3] *= height
                                        
                                        originalLocations.append(l.astype(int).tolist())
                                
                                detections = {
                                        'boxes': originalLocations,
                                        'scores': list(prob.tolist()),
                                        'classes': list(label.tolist())
                                }

                                # save to db
                                msg['detections'] = detections
                                self.updateDb(msg)

                                # dispatch to mq
                                self._publisher.publish_message(msg)

                except:
                        logger.error("An error occurred: ", exc_info=True)
                        #todo - post to mq

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

        ap.add_argument("--cls-threshold", type=float, default=0.3)
        ap.add_argument("--nms-threshold", type=float, default=0.5)
        ap.add_argument("--model", type=str, default="trained_models/SSD.pth")

        ap.add_argument("-cf", "--config.file", default='platedetector.yaml',
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


        detector = PlateDetector(args)
        detector.loop_forever()


