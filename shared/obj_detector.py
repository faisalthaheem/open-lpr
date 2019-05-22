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

import numpy as np
import os
import six.moves.urllib as urllib
import sys
import tarfile
import tensorflow as tf
import zipfile
import datetime
from .utils import tf_new_session

from collections import defaultdict
from io import StringIO
from PIL import Image

class ObjDetector:

    __graph__ = None
    __sess__ = None
    __input_tensor__ = None
    __detection_boxes__ = None
    __detection_scores__ = None
    __detection_classes__ = None
    __num_detections__ = None

    __categories__ = None
    __categories_index__ = None

    def init(self, modelPath, labelPath, device_id = "0",memory_fraction = 0.1): 

        self.__graph__ = tf.Graph()
        with self.__graph__.as_default():
            
            self.__sess__ = tf_new_session(device_id, memory_fraction)
            with self.__sess__.as_default():

                #detection_graph = tf.Graph()
                with tf.gfile.FastGFile(modelPath, 'rb') as f:
                    graph_def = tf.GraphDef()
                    graph_def.ParseFromString(f.read())
                    tf.import_graph_def(graph_def, name='')

        self.__input_tensor__ = self.__graph__.get_tensor_by_name('image_tensor:0')
        self.__detection_boxes__ = self.__graph__.get_tensor_by_name('detection_boxes:0')
        self.__detection_scores__ = self.__graph__.get_tensor_by_name('detection_scores:0')
        self.__detection_classes__ = self.__graph__.get_tensor_by_name('detection_classes:0')
        self.__num_detections__ = self.__graph__.get_tensor_by_name('num_detections:0')

    def detect(self, image_np_expanded):
        
        with self.__graph__.as_default():
            with self.__sess__.as_default():
                (boxes, scores, classes, num) = self.__sess__.run(
                        [self.__detection_boxes__, self.__detection_scores__, self.__detection_classes__, self.__num_detections__],
                        feed_dict={self.__input_tensor__: image_np_expanded}
                    )

                return (boxes, scores, classes, num)
