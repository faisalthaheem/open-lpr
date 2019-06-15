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
    __package__ = "ftp"
    
from shared.amqp import ThreadedAmqp

from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from pyftpdlib.authorizers import DummyAuthorizer

import queue
import argparse
import time
import pprint
import uuid
import sys
import signal
import os
import logging
import pickle
import threading
import yaml
import shutil
from pymongo import MongoClient

#create logger
logger = logging.getLogger('ftp.service')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('ftp.service.log')
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

ap = argparse.ArgumentParser()
ap.add_argument("-cf", "--config.file", default='ftp.service.yaml',
        help="Config file describing service parameters")
ap.add_argument("-bl", "--brokers.list", default='127.0.0.1',
        help="Kafka brokers")
args = vars(ap.parse_args())


## mq related
broker = None
queuedImages = queue.Queue(0)

# ftp related
server = None
dispatcherThread = None

config = None


def dispatcher():
    storagePath = config['storage']['path']
    logger.info("Will be storing all files to [{}]".format(storagePath))

    client = None
    db = None

    try:
        client = MongoClient(config['mongo']['uri'])

        #open db
        if not "openlpr" in client.database_names():
            logger.info("database openlpr does not exist, will be created after first document insert")
        
        db = client["openlpr"]

    except:
        logger.error("An error occurred: ", exc_info=True)

    while True:
        try:

            if queuedImages.qsize() > 0:

                qItm = queuedImages.get()

                msg = {}
                msg['_id'] = str(uuid.uuid4())
                msg['filename'] = qItm["filename"]
                msg['creationtime'] = qItm["creationtime"]

                # save to disk
                try:
                    unique_name = "{}_{}".format(msg['_id'], msg['filename'])
                    msg['unique_name'] = unique_name
                    destPath = os.path.join(storagePath, unique_name)
                    logger.info("Moving from [{}] to [{}]".format(qItm['diskpath'], destPath))
                    
                    shutil.move(qItm['diskpath'], destPath)

                except:
                    logger.error("An error occurred: ", exc_info=True)

                # save to db
                dbcollection = db["lprevents"]
                dbcollection.insert_one(msg)

            
                #post to mq
                broker.publish_message(msg)                
                logger.info("[{}] published".format(msg['_id']))

        except:
            logger.error("An error occurred: ", exc_info=True)

        if threading.main_thread().is_alive() is False:
            logger.info("Main thread exited, dispatcher exiting")
            return
        
        #sleep for configured period of time
        time.sleep(config['dispatcher']['period'])
        
        # break #commment to keep running


########## FTP Section
class MyHandler(FTPHandler):

    def on_connect(self):
        logger.info("%s:%s connected" % (self.remote_ip, self.remote_port))

    def on_disconnect(self):
        # do something when client disconnects
        pass

    def on_login(self, username):
        # do something when user login
        pass

    def on_logout(self, username):
        # do something when user logs out
        pass

    def on_file_sent(self, file):
        # do something when a file has been sent
        pass

    def on_file_received(self, file):
        try:
            file_name = os.path.basename(file)
                    
            fileInfo = {}
            fileInfo['filename'] = file_name
            fileInfo['creationtime'] = time.time()
            fileInfo['content'] = self.readFileContent(file)
            fileInfo['diskpath'] = file

            queuedImages.put(fileInfo)
            logger.info("Queued new file [{}]".format(file_name))
            
        except:
            logger.error("An error occurred: ", exc_info=True)
        pass
    
    def readFileContent(self, path):
        with open(path, 'rb') as content_file:
            return content_file.read()

    def on_incomplete_file_sent(self, file):
        # do something when a file is partially sent
        pass

    def on_incomplete_file_received(self, file):
        # remove partially uploaded files
        import os
        os.remove(file)


def main():

    global config
    global server
    global broker
    global dispatcherThread

    try:

        with open(args["config.file"]) as stream:
            try:
                if os.getenv('PRODUCTION') is not None: 
                        config = yaml.load(stream)['prod']
                else:
                        config = yaml.load(stream)['dev']

                pprint.pprint(config)
            except yaml.YAMLError as err:
                logger.error("An error occurred: ", exc_info=True)


        authorizer = DummyAuthorizer()
        authorizer.add_user('user', '12345', homedir='.', perm='elradfmwMT')
        authorizer.add_anonymous(homedir='.')

        logger.info("Connecting to broker")
        broker = ThreadedAmqp()
        brokerUrl = None

        brokerUrl = config['broker']['uri']
        logger.info("Using broker url [{}]".format(brokerUrl))

        broker.init(
            brokerUrl
        )
        broker.start()

        dispatcherThread = threading.Thread(None, dispatcher)
        dispatcherThread.start()
        
        handler = MyHandler
        handler.authorizer = authorizer

        server = FTPServer(('0.0.0.0', 2121), handler)
        server.serve_forever()
    except:
        logger.error("An error occurred: ", exc_info=True)

def signal_handler(sig, frame):
    try:
        logger.info("Ctrl-c pressed, stopping")
        server.close_all()
        broker.stop()
        dispatcherThread.stop()
    except:
        logger.error("An error occurred: ", exc_info=True)
    
#handle ctrl-c
signal.signal(signal.SIGINT, signal_handler)
main()
