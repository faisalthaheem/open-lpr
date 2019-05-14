# Ugly hack to allow absolute import from the root folder
# whatever its name is. Please forgive the heresy.
if __name__ == "__main__" and __package__ is None:
    from sys import path
    from os.path import dirname as dir

    path.append(dir(path[0]))
    __package__ = "openalpr_ftp"
    
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
ap.add_argument("-sp", "--storage.path", default='/data',
        help="Storage Path")
args = vars(ap.parse_args())


## mq related
broker = None
queuedImages = queue.Queue(0)

# ftp related
server = None
dispatcherThread = None

with open(args["config.file"]) as stream:
    try:
        config = yaml.load(stream)
        pprint.pprint(config)
    except yaml.YAMLError as err:
        logger.error(err)


def dispatcher():
    storagePath = args['storage.path']
    logger.info("Will be storing all files to [{}]".format(storagePath))

    while True:
        try:

            if queuedImages.qsize() > 0:

                qItm = queuedImages.get()

                msg = {}
                msg['eventid'] = str(uuid.uuid4())
                msg['filename'] = qItm["filename"]
                msg['creationtime'] = qItm["creationtime"]

                # save to disk
                try:
                    destPath = os.path.join(storagePath, "{}_{}".format(msg['eventid'], msg['filename']))
                    msg['diskpath'] = destPath
                    logger.info("Moving from [{}] to [{}]".format(qItm['diskpath'], destPath))
                    
                    shutil.move(qItm['diskpath'], msg['diskpath'])

                except:
                    logger.error(sys.exc_info())

                # save to db
            
                #post to mqtt
                broker.publish_message(msg)                
                logger.info("[{}] published".format(msg['eventid']))

        except:
            logger.error(sys.exc_info())

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
            logger.error(sys.exc_info())
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

    global server
    global broker
    global dispatcherThread

    try:
        authorizer = DummyAuthorizer()
        authorizer.add_user('user', '12345', homedir='.', perm='elradfmwMT')
        authorizer.add_anonymous(homedir='.')

        logger.info("Connecting to broker")
        broker = ThreadedAmqp()
        broker.init(
            'amqp://guest:guest@localhost:5672/%2F?connection_attempts=3&heartbeat=3600'
        )
        broker.start()

        dispatcherThread = threading.Thread(None, dispatcher).start()
        
        handler = MyHandler
        handler.authorizer = authorizer

        server = FTPServer(('0.0.0.0', 2121), handler)
        server.serve_forever()
    except:
        logger.error(sys.exc_info())

def signal_handler(sig, frame):
    try:
        logger.info("Ctrl-c pressed, stopping")
        server.close_all()
        broker.stop()
        dispatcherThread.stop()
    except:
        logger.error(sys.exc_info())
    
#handle ctrl-c
signal.signal(signal.SIGINT, signal_handler)
main()
