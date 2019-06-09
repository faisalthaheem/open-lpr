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
import cv2
import sys
import math
import time
import pprint
import scipy.misc
import traceback
import random
import os

from skimage.transform import resize

class CvFuncs:
    
    #plate control
    _is_broad = False
    #normal plates
    _charHeightMin = 34
    _charHeightMax = 58
    _n_vertical_deviation = 25

    #broad plates
    _b_charHeightMin = 34
    _b_charHeightMax = 58
    _b_vertical_deviation = 30

    #common filters
    _min_char_width = 5
    
    #the maximum width of the bounding box of detected contours... boxes such as the ones encompassing the whole plate are eliminated to
    #not let them impact the weights and cogs and average widths
    _box_width_max = 80
    _neighbor_gap_max = 15 #how many pixels can the group of character's bounding rects be apart
    _xDeviation = 10 #in pixels
    _yDeviation = 10 #in pixels

    debugEnabled = False #generates crazy amount of intermediate images which are useful for debugging
    imageStoreDir = "" #location of images to store at
    currentlyProcessedFileName = ""
    
    #data type of records in the list
    dtype_letter_rect = [('x',int),('y',int),('w',int),('h',int),('cogx',float),('cogy',float),('weight',int),('area',int)]
    brects_unsorted = []
    brects_sorted = []
    processed_cogx_list = []
    processed_cogy_list = []
    potential_char_height_avg = 0
    y_avg = 0
    box_width_avg = 0
    max_allowed_char_width = 0
    eligible_box_area_avg = 0
    _width = 0
    _height = 0
    average_color = 0

    #timings
    time_taken_by_skewCorrection = 0
    time_taken_by_analyzeRects = 0
    time_taken_by_breakupBoxesAndCalcWeights = 0
    time_taken_by_eliminateByCog = 0
    time_taken_by_eliminateByArea = 0
    time_taken_by_determineBlackOrWhite = 0
    time_taken_by_findAndAppendContours = 0
    time_taken_by_extractLetters = 0
    time_taken_by_findRectsNormalCase = 0
    time_taken_by_assignNeighborWeights = 0
    time_taken_by_eliminateByYDeviation = 0

    #images
    plate = None #the extracted plate region from the input image
    thresh = None # this is the image we extract letters from
    masked = None
    white_bg = None

    def reset(self):
        self.brects_unsorted = []
        self.brects_sorted = []
        self.processed_cogx_list = []
        self.potential_char_height_avg = 0
        self.y_avg = 0
        self.box_width_avg = 0
        self.max_allowed_char_width = 0
        self.eligible_box_area_avg = 0
        self._width = 0
        self._height = 0
        self.average_color = 0

        #timings
        self.time_taken_by_skewCorrection = 0
        self.time_taken_by_analyzeRects = 0
        self.time_taken_by_breakupBoxesAndCalcWeights = 0
        self.time_taken_by_eliminateByCog = 0
        self.time_taken_by_eliminateByArea = 0
        self.time_taken_by_determineBlackOrWhite = 0
        self.time_taken_by_findAndAppendContours = 0
        self.time_taken_by_extractLetters = 0
        self.time_taken_by_findRectsNormalCase = 0
        self.time_taken_by_assignNeighborWeights = 0
        self.time_taken_by_eliminateByYDeviation = 0

        #images
        self.plate = None #the extracted plate region from the input image
        self.thresh = None # this is the image we extract letters from
        self.masked = None
        self.white_bg = None

    def makeIntermediateFileName(self, originalFilename, auxFileName):
        return "{}/{}_{}.jpg".format(self.imageStoreDir, originalFilename, auxFileName)

    def randomColor(self):
        return (255*random.random(), 255*random.random(), 255*random.random())

    def saveRoundImage(self, round, filename, forceSave = False):
        """Utility function for saving images with
         highlighted brects_sorted drawn
        """
        
        if not self.debugEnabled and forceSave is False:
            return

        round_img = self.plate.copy()
        i = 0
        while i < len(self.brects_sorted):
            x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[i]
            cv2.rectangle(round_img, (x, y), (x + w, y + h), self.randomColor(), 1)
            i = i + 1

        #round_img_filename = "{}.round.{}.png".format(filename, round)
        round_img_filename = self.makeIntermediateFileName(filename, round)

        debugPath = os.path.join('.','debug')
        if not os.path.exists(debugPath):
            os.makedirs(debugPath)

        filePath = os.path.join(debugPath, round_img_filename)
        cv2.imwrite(filePath, round_img)
    
    def correct_skew(self, image):

        timeStart = time.time()

        #copied from http://www.pyimagesearch.com/2017/02/20/text-skew-correction-opencv-python/
        #gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.bitwise_not(image)
        thresh = cv2.threshold(gray, 0, 255,
            cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(thresh > 0))
        angle = cv2.minAreaRect(coords)[-1]
        
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        # rotate the image to deskew it
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(image, M, (w, h),
            flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

        self.time_taken_by_skewCorrection = time.time() - timeStart
            
        return rotated

    def analyzeRects(self,filename):
        """Round 1
            pre process - calculate averages, avg width, avg height etc
            Gather statistics on the sorted rects for decision making
            Filters out rects which do not fall between the valid character heights min
            and max.

            Call after all rects have been found
        """

        timeStart = time.time()

        potential_letters_y_sum =0
        potential_letters_count = 0
        potential_letters_height_sum =0
        box_width_sum =0
        box_width_count = 0
        average_gap_sum = 0 #todo calculate and then exclude those which have more gap with the rest of the group

        i = 0
        while i < len(self.brects_sorted):
            
            x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[i]
            valid_roi = False
            
            if ((h >= self._charHeightMin and h <= self._charHeightMax) and w >= self._min_char_width):
                valid_roi = True

            if valid_roi and w <= self._box_width_max:
                box_width_sum = box_width_sum + w
                box_width_count = box_width_count + 1

                potential_letters_y_sum = potential_letters_y_sum + y
                potential_letters_height_sum = potential_letters_height_sum + ((y+h)-y)
                potential_letters_count = potential_letters_count + 1
            else:
                #print("del {}".format(self.brects_sorted[i]))
                self.brects_sorted = np.delete(self.brects_sorted, i)
                continue
            
            #process next
            i = i+1

        #avoid divide by 0 errors..
        if potential_letters_count == 0:
            potential_letters_count = 1 

        if box_width_count == 0:
            box_width_count = 1

        if len(self.brects_sorted) == 0:
            return

        self.potential_char_height_avg = int(potential_letters_height_sum/potential_letters_count)
        self.y_avg = int(self._height / 2)
        self.box_width_avg = int(box_width_sum / box_width_count)
        # self.max_allowed_char_width = int(self.box_width_avg)
        

        if(self.debugEnabled):
            #save round image
            self.saveRoundImage('analyze-rects',filename)
            print("y_avg [{}] box_width_avg [{}] max_allowed_char_width[{}] potential_char_height_avg[{}]" .format(self.y_avg, self.box_width_avg, self.max_allowed_char_width, self.potential_char_height_avg))
            print("Round 1 rects are: {}".format(len(self.brects_sorted)))
            pprint.pprint(self.brects_sorted)

        self.time_taken_by_analyzeRects = time.time() - timeStart

    def eliminateByYDeviation(self, filename):

        timeStart = time.time()

        v_deviation = self._n_vertical_deviation
        # if self._is_broad:
        #     v_deviation = self._b_vertical_deviation

        imgh,imgw = self.thresh.shape

        imgh = imgh // 2

        i = 0
        while i < len(self.brects_sorted):
            x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[i]
            
            if self.debugEnabled:
                print("y[{}] y_avg[{}] abs(y-y_avg)[{}] v_dev[{}] [{}]".format( y, self.y_avg, abs(y-self.y_avg), v_deviation, self.brects_sorted[i]))
                
            # if (abs(y-self.y_avg) > v_deviation):
            if abs(y-imgh) > 30:
                #remove the rect as it is not what we are interested in
                if self.debugEnabled:
                    print("del for y_deviation [{}] <--\n".format(self.brects_sorted[i]))
                self.brects_sorted = np.delete(self.brects_sorted, i)
                continue

            
            #process next
            i = i + 1
            
        self.brects_sorted = np.sort(self.brects_sorted, order=['x'])

        if self.debugEnabled:
            #save round image
            self.saveRoundImage('y_deviation',filename)
            print("eliminateByYDeviation leaving with [{}] rects".format(len(self.brects_sorted)))
            pprint.pprint(self.brects_sorted)

        self.time_taken_by_eliminateByYDeviation = time.time() - timeStart


    def breakupBoxesAndCalcWeights(self,filename):
        """Round 2
            pre process - breakup any wider boxes into smaller ones of average char width
            and calculate weights based on how close a neighbor, for consecutive letters, the 
            gap between (x+w) and w of next box must be less than "padding"
        """

        timeStart = time.time()

        eligible_box_area_sum = 0
        eligible_box_count = 0
        i = 0
        while i < len(self.brects_sorted):
            x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[i]
                
            #outright discard boxes > 3 x max_allowed_char_width as that's noise
            if  (w > 3*self.max_allowed_char_width):
                if self.debugEnabled:
                    print("Round 2 - del for 3*max_allowed_char_width({}) [{}]\n".format(3*self.max_allowed_char_width,self.brects_sorted[i]))
                self.brects_sorted = np.delete(self.brects_sorted, i)
                continue

            if(h<20):
                if self.debugEnabled:
                    print("h<20 [{}]\n".format(self.brects_sorted[i]))
                self.brects_sorted = np.delete(self.brects_sorted, i)
                continue

            if (w > self.max_allowed_char_width):
            # if (w > h):
                
                boxes_to_breakup_into = 2
                #width_per_box = w / boxes_to_breakup_into
                width_per_box = w / 2
                #print("w[{}] max_w[{}] parts[{}] - box [{},{},{},{}]".format(w,2, boxes_to_breakup_into, x,y,w,h))
                
                if boxes_to_breakup_into > 1:
                    #remove this box from brects_sorted
                    self.brects_sorted = np.delete(self.brects_sorted, i)

                    for ibox in range(0, boxes_to_breakup_into):
                        #print( "new region x[{}] y[{}] w[{}] h[{}]\n".format(x+ (ibox*width_per_box), y, width_per_box,h))
                        nx = x+ (ibox*width_per_box)
                        
                        ncogx = (nx + (nx+width_per_box))/2
                        ncogy = (y + (y+h))/2

                        self.brects_sorted = np.append(
                            self.brects_sorted,
                            np.array([
                                (nx, y, width_per_box,h,ncogx,cogy,0,width_per_box*h)
                                ], dtype=self.dtype_letter_rect)
                        )
                    #dont increment index as current was deleted and the next one 
                    #is already in it's place	
                    continue
                else: #see below... increment to next element
                    eligible_box_area_sum = eligible_box_area_sum + (w*h)
                    eligible_box_count = eligible_box_count + 1
            else:
                eligible_box_area_sum = eligible_box_area_sum + (w*h)
                eligible_box_count = eligible_box_count + 1

            
            #process next
            i = i + 1
            
        self.brects_sorted = np.sort(self.brects_sorted, order=['x'])

        #avoid divide by 0 errors
        if eligible_box_count ==0:
            eligible_box_count = eligible_box_count + 1

        self.eligible_box_area_avg = eligible_box_area_sum/eligible_box_count


        if self.debugEnabled:
            #save round image
            self.saveRoundImage('newRects',filename)
            print("breakupBoxesAndCalcWeights rects are: {}".format(len(self.brects_sorted)))
            pprint.pprint(self.brects_sorted)

        self.time_taken_by_breakupBoxesAndCalcWeights = time.time() - timeStart


    def cog_doElimination(self,filename):
        #sort by width so that smaller boxes are kept and larger are eliminated
        # self.brects_sorted=np.sort(self.brects_sorted, order=['w'])

        i = 0
        
        while i < len(self.brects_sorted):
            x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[i]
            
            if self.debugEnabled:
                print("Comparing [{}][{}]@[{}]".format(cogx, cogy, self.brects_sorted[i]))

            j = i+1

            while j < len(self.brects_sorted):

                x_j,y_j,w_j,h_j,cogx_j,cogy_j,wr_j,area_j = self.brects_sorted[j]

                if self.debugEnabled:
                    print("\t with [{}][{}]@[{}]".format(cogx_j, cogy_j, self.brects_sorted[j]))

                found_gx = False
                found_gy = False

                
                if abs(cogx_j-cogx) <= self._xDeviation:
                    found_gx = True

                if abs(cogy_j-cogy) <= self._yDeviation:
                    found_gy = True

                if found_gx and found_gy:
                    if self.debugEnabled:
                        print("deleted (j) cog[{}][{}]@[{}]  <--\n".format(cogx,cogy, self.brects_sorted[j]))

                    self.brects_sorted = np.delete(self.brects_sorted, j)
                    #break
                else:
                    j = j+1
                

            i = i + 1

        # #restore ordering to order by x
        # self.brects_sorted=np.sort(self.brects_sorted, order=['x'])

        if self.debugEnabled:
            #save round image
            self.saveRoundImage('cog',filename)
            print("[cog] round rects are: {}".format(len(self.brects_sorted)))
            pprint.pprint(self.brects_sorted)

    def eliminateByCog(self, filename):

        #print("eliminateByCog entered")
        timeStart = time.time()
        
        self.cog_doElimination(filename)

        self.time_taken_by_eliminateByCog = self.time_taken_by_eliminateByCog + (time.time() - timeStart)
        #print("eliminateByCog exiting")

    def doRectsOverlap(self, r1l,r1r,r1t,r1b, r2l, r2r, r2t, r2b):
        """
            https://stackoverflow.com/questions/306316/determine-if-two-rectangles-overlap-each-other
        """
        return (r1l < r2r and r1r > r2l and r1t > r2b and r1b < r2t)

    def eliminateByOverlap(self):
        """
            Compares every rect with others and
            Discards one of the two rects with larger area
        """

        #print("eliminateByOverlap entered")

        #we make copy of the brects_sorted as we will be sorting by area
        sorted_rects = np.sort(self.brects_sorted, order=['area'])

        i = 0
        while i < len(sorted_rects)-1:
            x1,y1,w1,h1,cogx1,cogy1,wr1,area1 = sorted_rects[i]
            x2,y2,w2,h2,cogx2,cogy2,wr2,area2 = sorted_rects[i+1]
            #print("eliminateByOverlap entered 2")
            #eliminated = False
            if self.doRectsOverlap(x1,x1+w1, y1, y1+h1, x2, x2+w2, y2, y2+h2):
            #    eliminated = True

                msg = "Deleting rect at: "

                #eliminate the larger of the two rects
                if area1 > area2:
                    sorted_rects = np.delete(sorted_rects, i)
                    msg = msg + str(i)
                else:
                    sorted_rects = np.delete(sorted_rects, i+1)
                    msg = msg + str(i+1)
                    i = i + 1 #process next

                if self.debugEnabled:
                    print(msg)
            
            else:
                i = i+1
        
        #restore x sorted array
        self.brects_sorted = np.sort(sorted_rects, order=['x'])

        #print("eliminateByOverlap exiting")

        if self.debugEnabled:
            #save round image
            self.saveRoundImage('overlap',self.currentlyProcessedFileName)
            print("eliminateByOverlap rects are: {}".format(len(self.brects_sorted)))
            pprint.pprint(self.brects_sorted)

    def filterPreExtract(self):
        """
            Removes empty white only boxes
            Removes boxes which have a height less that avg(h)-threshold
        """

        print("filterPreExtract entered")

        #we make copy of the brects_sorted as we will be sorting by area
        sorted_rects = np.sort(self.brects_sorted, order=['area'])

        i = 0
        avgHeight = 0
        avgWidth = 0
        while i < len(self.brects_sorted):

            x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[i]
            cropped_letter = self.thresh[y:y+h, x:x+w]
            colorAvg = self.detectColor(cropped_letter)
            print("colorAvg is ", colorAvg)
            #pprint.pprint(cropped_letter) 
            if colorAvg > 220:
                #if more than 50% image is white it's not a valid character.. since characters are supposed to be in black and occupy
                #most of their box
                print("Removing ", self.brects_sorted[i], "due to color")
                self.brects_sorted = np.delete(self.brects_sorted, i)
                continue
                
            avgHeight = avgHeight + h
            avgWidth = avgWidth + w
            i = i + 1  # process next rect

        avgHeight = avgHeight / len(self.brects_sorted)
        avgWidth = avgWidth / len(self.brects_sorted)
        print("Avg Width: ", avgWidth, " Avg Height: ", avgHeight)

        i = 0
        while i < len(self.brects_sorted):

            x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[i]
            
            if h < (avgHeight - 3):
                print("Removing ", self.brects_sorted[i], "due to height")
                self.brects_sorted = np.delete(self.brects_sorted, i)
                continue

            if w > (avgWidth + 5):
                print("Removing ", self.brects_sorted[i], "due to width")
                self.brects_sorted = np.delete(self.brects_sorted, i)
                continue
                
            i = i + 1  # process next rect
      
        print("filterPreExtract exiting")

        if self.debugEnabled:
            #save round image
            self.saveRoundImage('filterPreExtract',self.currentlyProcessedFileName)
            print("filterPreExtract rects are: {}".format(len(self.brects_sorted)))
            pprint.pprint(self.brects_sorted)

    def eliminateByArea(self,filename):
        """Round 3
            pre filtering, find average area of eligible boxes and remove the boxes
            which have already been processed (with help of cogx)
        """
        
        timeStart = time.time()
        
        i = 0
        
        while i < len(self.brects_sorted):
            x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[i]
                
            box_area = w*h

            eligible_box_area_min =  self.eligible_box_area_avg*0.3
            eligible_box_area_max = self.eligible_box_area_avg + (self.eligible_box_area_avg*0.66)
            
            if self.debugEnabled:
                print("eligible_box_area_avg[{}] eligible_box_area_min[{}] eligible_box_area_max[{}]".format(
                    self.eligible_box_area_avg,eligible_box_area_min, eligible_box_area_max))

            if (box_area >= eligible_box_area_min and box_area <= eligible_box_area_max):
                
                i = i + 1
            else:
                if self.debugEnabled:
                    print("elimination by area[{}] max:[{}] @ [{}]  <--\n".format(box_area,self.eligible_box_area_avg,self.brects_sorted[i]))
                
                #delete corresponding cog from list if exists
                self.brects_sorted = np.delete(self.brects_sorted, i)

        if self.debugEnabled:
            #save round image
            self.saveRoundImage('area',filename)
            print("Round 3 rects are: {}".format(len(self.brects_sorted)))
            pprint.pprint(self.brects_sorted)

        self.time_taken_by_eliminateByArea = time.time() - timeStart

    def findGap(self, rect1, rect2):
        """
            Finds the distance between the rect1(x2) and rect2(x1)
        """
        return abs( rect2['x'] - (rect1['x']+rect1['w']) )


    def limitToCenterLetters(self,filename):
        """Round 3
            pre filtering, if there are more than 6 letters in the image.. we select the middle 6.
            this is specific to qatar plates.. need more r&d
        """
        numChars = len(self.brects_sorted)
        if numChars <=6:
            return

        if numChars&1 == 1:
            #if there are odd number of characters, we choose either left or right based on 
            #which side digit has lesser space with it's neighbor
            #odd number of characters.. convert to even
            gapLeft = self.findGap(self.brects_sorted[0], self.brects_sorted[1])
            gapRight = self.findGap(self.brects_sorted[numChars-2], self.brects_sorted[numChars-1])


            if gapLeft < gapRight:
                #trim the char at the end (right of the string)
                self.brects_sorted = np.delete(self.brects_sorted, numChars-1)
            else:
                #trim the char at the start (left of the string)
                self.brects_sorted = np.delete(self.brects_sorted, 0)

        #handle the case of 7 chars
        numChars = len(self.brects_sorted)
        if numChars <=6:
            return
        
        #even number of characters.. trim equally on both sides
        extra_letters = numChars - 6
        extra_letters = math.ceil(extra_letters/2)
        
        for i in range(0, extra_letters):
            self.brects_sorted = np.delete(self.brects_sorted, 0)
            self.brects_sorted = np.delete(self.brects_sorted, len(self.brects_sorted)-1)

        
        if self.debugEnabled:
            #save round image
            self.saveRoundImage('limitToCenterLetters',filename)

    def getWeightToRight(self, caller_border_x, i):
        """
            caller_border_x is x+w of the rect
        """
        #print(caller_border_x,i)
        if i >= len(self.brects_sorted):
            return 0

        while i < len(self.brects_sorted):
            x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[i]

            if abs(x-caller_border_x) > self._neighbor_gap_max:
                return 0
            
            return 1 + self.getWeightToRight((x+w), i+1)
    

    def getWeightToLeft(self, caller_border_x, i):
        """
            caller_border_x is the 'x' of the rect since we are going left
        """
        #print(caller_border_x,i)
        if i < 0:
            return 0

        while i >= 0:
            x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[i]

            if abs((x+w)-caller_border_x) > self._neighbor_gap_max:
                return 0
            
            return 1 + self.getWeightToLeft(x, i-1)


    def assignNeighborWeights(self, filename):
        """Assigns each rect a weight by summing neighbors within a defined proximity to the left and right
            At the end of the process we can identify the group of letters and discard the ones which have lesser weigh than the most consecutive characters in the image
        """
        timeStart = time.time()

        highest_weight = 0

        i = 0
        while i < len(self.brects_sorted):
            x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[i]

            #calculate to the left
            weight = self.getWeightToLeft(x,i-1)
            #print()

            #calculate to the right
            weight = weight + self.getWeightToRight((x+w), i+1)
            self.brects_sorted[i]['weight'] = weight

            if weight > highest_weight:
                highest_weight = weight

            #print("--")
            i = i+1

        if self.debugEnabled:
            print("assignNeighborWeights, assigned weights",self.brects_sorted)
            print("assignNeighborWeights - will remove all rects with weights lower than ", highest_weight)

        #now remove all rects which have a lower weight that highest_weight
        i = 0
        while i < len(self.brects_sorted):
            x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[i]

            if wr < highest_weight:
                self.brects_sorted = np.delete(self.brects_sorted, i)
                continue
            
            i = i+1

        if self.debugEnabled:
            #save round image
            self.saveRoundImage('weights',filename)
            print("After assignNeighborWeights rects are: {}".format(len(self.brects_sorted)))
            pprint.pprint(self.brects_sorted)

        self.time_taken_by_assignNeighborWeights = time.time() - timeStart

    def detectColor(self, img):
                
        return np.average(img)


    def determineBlackOrWhite(self, filename):
        """Round 4
            determine blackness - do not move this elsewhere as if we do not stay around the
            characters we may end up accounting for the border area of the plate which may give wrong results
            http://miriamposner.com/classes/medimages/3-use-opencv-to-find-the-average-color-of-an-image/
        """
        
        timeStart = time.time()

        self.average_color = self.detectColor(self.thresh)

        self.time_taken_by_determineBlackOrWhite = time.time() - timeStart

    def fitLetters(self, letters, width = 48, height = 48):

        #we base our fitting on 2nd member of the list
        if len(letters) < 2:
            return

        height, width = letters[0].shape

        aspect_ratio = height/width #normally the letters are taller

        #given the width of 48, find the height
        height = int(aspect_ratio * width)

        print("Resizing all letters to h,w",height, width)

        blank_image = np.zeros((96,96,3), np.uint8) #graph was trained on 96,96 sized images
        blank_image[0:96,0:96] = (255,255,255)

        #https://stackoverflow.com/questions/6086621/how-to-reduce-an-image-size-in-image-processing-scipy-numpy-python
        #https://stackoverflow.com/questions/21596281/how-does-one-convert-a-grayscale-image-to-rgb-in-opencv-python-for-visualizing/21709613
        #for all members of the list.. resize
        for i in range(0, len(letters)):
            
            #letters[i] = np.resize(letters[i], (height,width,3))
            letters[i] = cv2.cvtColor(letters[i],cv2.COLOR_GRAY2RGB)
            #letters[i] = scipy.misc.imresize(letters[i], (height, width))
            blank = blank_image.copy()
            blank[20: 20 + letters[i].shape[0], 20: 20+letters[i].shape[1]] = letters[i]

            letters[i] = blank
             
            
        return letters

    def getOverlappingArea(self, x1,y1,w1,h1, x2,y2,w2,h2):

        dx = min(x1+w1, x2+w2) - max(x1, x2)
        dy = min(y1+h1, y2+h2) - max(y1, y2)
        if (dx>=0) and (dy>=0):
            return dx*dy
        
        return 0.0

    def nonLocalMaxima(self):
        print("nonLocalMaxima entered")
        self.saveRoundImage('before.nonLocalMaxima','forceextract.jpg')
        
        if len(self.brects_sorted) < 2:
            print("nonLocalMaxima exiting, <2 sorted rects")            
            return

        i = 0
        while i < len(self.brects_sorted)-1:

            x1,y1,w1,h1,cogx,cogy,wr,area = self.brects_sorted[i]
            x2,y2,w2,h2,cogx1,cogy1,wr1,area1 = self.brects_sorted[i+1]

            if self.getOverlappingArea(x1,y1,w1,h1, x2,y2,w2,h2) >= 0.5:
                nx = min(x1,x2)
                nw = max(x1+w1, x2+w2)
                ny = min(y1,y2)
                nh = max(y1+h1, y2+h2)
                ncogx = (nx + (nx+nw))/2
                ncogy = (ny + (ny+nh))/2
                narea = nw*nh

                newRoi = np.array([(nx, ny, nw, nh, ncogx, ncogy, 0 ,narea)],
                    dtype=self.dtype_letter_rect)
                if self.debugEnabled:
                    pprint.pprint(newRoi)
                    

                self.brects_sorted = np.append(
                    self.brects_sorted,
                    newRoi
                )

                #delete at i and i+1
                self.brects_sorted = np.delete(self.brects_sorted, i+1)
                self.brects_sorted = np.delete(self.brects_sorted, i)

            else:
                i = i+1

        self.brects_sorted=np.sort(self.brects_sorted, order=['x'])

        print("nonLocalMaxima exiting")
        self.saveRoundImage('after.nonLocalMaxima','forceextract.jpg')
    
    # takes sorted brects and if there is sufficient space to the left
    # it adds a roi based on estimation for cases where the letters on the left 
    # adjoin the wavy plate design
    # classification will eliminate any non letters
    def discoverToLeft(self):

        if self.debugEnabled:
            print("discoverToLeft entered")
            self.saveRoundImage('before.discoverToLeft','discoverToLeft.jpg')
            
        if len(self.brects_sorted) < 2:
            if self.debugEnabled:
                print("discoverToLeft exiting, <2 sorted rects")            
            return

        x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[0]
        x1,y1,w1,h1,cogx1,cogy1,wr1,area1 = self.brects_sorted[1]

        padding = x1 - (x+w)
        
        if (x-w) >= 0:
            # how many rois can we be extracted
            numRects = x//w
            if self.debugEnabled:
                print("numrects:", numRects)

            for i in range(1, numRects):
                nx = x - ((i*w) + padding)
                nw = w
                ny = y
                nh = h
                ncogx = (nx + (nx+w))/2
                ncogy = (y + (y+h))/2
                narea = nw*nh

                if nx < 0:
                    break

                newRoi = np.array([(nx, ny, nw, nh, ncogx, ncogy, 0 ,narea)],
                    dtype=self.dtype_letter_rect)
                if self.debugEnabled:
                    pprint.pprint(newRoi)
                    

                self.brects_sorted = np.append(
                    self.brects_sorted,
                    newRoi
                )

        self.brects_sorted=np.sort(self.brects_sorted, order=['x'])

        if self.debugEnabled:
            print("discoverToLeft exiting")
            self.saveRoundImage('after.discoverToLeft','discoverToLeft.jpg')

    def discoverToRight(self):

        if self.debugEnabled:
            print("discoverToRight entered")
            self.saveRoundImage('before.discoverToRight','discoverToRight.jpg')
            
        if len(self.brects_sorted) < 2:
            if self.debugEnabled:
                print("discoverToRight exiting, <2 sorted rects")            
            return

        img_h, img_w = self.thresh.shape

        x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[-2]
        x1,y1,w1,h1,cogx1,cogy1,wr1,area1 = self.brects_sorted[-1]

        padding = x1 - (x+w)
        
        if (x1 + w1 + padding) < img_w:
            # how many rois can we be extracted
            numRects = (img_w - (x1+w1))//w
            if self.debugEnabled:
                print("numrects:", numRects)

            for i in range(0, numRects):
                nx = x1+w1 + ((i*w1) + padding)
                nw = w1
                ny = y1
                nh = h1
                ncogx = (nx + (nx+nw))/2
                ncogy = (ny + (ny+nh))/2
                narea = nw*nh

                if nx >= img_w or (nx+nw) >= img_w:
                    break

                newRoi = np.array([(nx, ny, nw, nh, ncogx, ncogy, 0 ,narea)],
                    dtype=self.dtype_letter_rect)
                if self.debugEnabled:
                    pprint.pprint(newRoi)

                self.brects_sorted = np.append(
                    self.brects_sorted,
                    newRoi
                )

        self.brects_sorted=np.sort(self.brects_sorted, order=['x'])

        if self.debugEnabled:
            print("discoverToRight exiting")
            self.saveRoundImage('after.discoverToRight','discoverToRight.jpg')
    
    def discoverInMiddle(self):

        if self.debugEnabled:
            print("discoverInMiddle entered")
            self.saveRoundImage('before.discoverInMiddle','discoverInMiddle.jpg')
            
        if len(self.brects_sorted) < 2:
            if self.debugEnabled:
                print("discoverInMiddle exiting, <2 sorted rects")            
            return

        #get median box width
        min_w = np.min(self.brects_sorted['w'])
        mean_w = int(np.mean(self.brects_sorted['w']))
        max_w = np.max(self.brects_sorted['w'])

        if self.debugEnabled:
            print("min_w",min_w)
            print("mean_w",mean_w)
            print("max_w",max_w)

        #look to the right, if the distanace between current box and next box is > than mean_w then
        # calculate how many boxes to insert
        #   insert a boxes

        for i in range(0, len(self.brects_sorted)-1):
            x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[i]
            x1,y1,w1,h1,cogx1,cogy1,wr1,area1 = self.brects_sorted[i+1]

            gap = abs(x1-(x+w))

            if self.debugEnabled:
                print("x|x+w|gap = {}|{}|{}".format(x,x+w,gap))

            if gap > mean_w:
                numBoxesToInsert = gap // mean_w

                prev_box_end = (x+w)
                for j in range(0, numBoxesToInsert):
                    nx = prev_box_end + 5
                    nw = mean_w
                    ny = y
                    nh = h
                    ncogx = (nx + (nx+nw))/2
                    ncogy = (y + (y+nh))/2
                    narea = nw*nh

                    prev_box_end = nx + nw
            
                newRoi = np.array([(nx, ny, nw, nh, ncogx, ncogy, 0 ,narea)],
                    dtype=self.dtype_letter_rect)

                if self.debugEnabled:
                    pprint.pprint(newRoi)
                    
                self.brects_sorted = np.append(
                    self.brects_sorted,
                    newRoi
                )

        self.brects_sorted=np.sort(self.brects_sorted, order=['x'])

        if self.debugEnabled:
            print("discoverInMiddle exiting")
            self.saveRoundImage('after.discoverInMiddle','discoverInMiddle.jpg')

    def eliminateByAvgHeight(self):

        if self.debugEnabled:
            self.saveRoundImage('before.eliminateByAvgHeight','test')
            print("eliminateByAvgHeight entered")

        min_height = np.min(self.brects_sorted['h'])
        mean_height = np.mean(self.brects_sorted['h'])
        max_height = np.max(self.brects_sorted['h'])

        if abs(max_height - min_height) < 5:
            #do nothing, as the difference in height among all rois is very small
            if self.debugEnabled:
                print("eliminateByAvgHeight exiting. max-min height diff is < 5")
            return

        allowed_deviation = max_height-mean_height

        if self.debugEnabled:
            print("min_height",min_height)
            print("mean_height",mean_height)
            print("max_height",max_height)
            
        i = 0
        while i < len(self.brects_sorted):
            x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[i]

            if abs(h-mean_height) > allowed_deviation:
                self.brects_sorted = np.delete(self.brects_sorted, i)
            else:
                i += 1
        
        #self.brects_sorted=np.sort(self.brects_sorted, order=['x'])

        if self.debugEnabled:
            self.saveRoundImage('after.eliminateByAvgHeight','test')
            print("eliminateByAvgHeight exiting")
        
    
    def findAndAppendContours(self, img):

        timeStart = time.time()

        localImg = img.copy()

        contours, hierarchy = cv2.findContours(localImg, cv2.RETR_LIST , cv2.CHAIN_APPROX_SIMPLE)
        if self.debugEnabled:
            print("findAndAppendContours Found [{}] contours".format(len(contours)))

        for c in contours:
            x,y,w,h = cv2.boundingRect(c)
            cogx = (x + (x+w))/2
            cogy = (y + (y+h))/2
            area = w*h
            self.brects_unsorted.append((x,y,w,h,cogx,cogy,0,area))

        self.time_taken_by_findAndAppendContours = self.time_taken_by_findAndAppendContours + (time.time() - timeStart)

        return len(contours)

    def extractLetters(self, filename):
        """Round 4, finally crop letters and paste on white bg
        """

        letters = []
        timeStart = time.time()
        self.resetBlanks()

        i = 0
        #print(brects_sorted)
        while i < len(self.brects_sorted):
            x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[i]
            i = i + 1

            if self.debugEnabled:
                print("w[{}] max_allowed_char_width[{}]".format(w,self.max_allowed_char_width))

            if (w/self.max_allowed_char_width) > 0.2:
                
                cv2.rectangle(self.masked, (x, y), (x + w, y + h), (255,255,255), -1)

                #extract part of image
                if self.debugEnabled:
                    print("Extracting digit i[{}] x[{}] y[{}] w[{}] h[{}] cog[{}] w[{}]".format(i,x,y,w,h,cogx,wr))

                cropped_letter = self.thresh[y:y+h, x:x+w]
                #if too black then invert so that text is black and surrounding is white
                #from testing, if average is below 120 we have a letter with black background
                if self.average_color <125:
                    cropped_letter = cv2.bitwise_not(cropped_letter)

                letters.append(cropped_letter)

                # if self.debugEnabled:
                # 	cropped_letter_resized = cv2.resize(cropped_letter,(13,22),interpolation = cv2.INTER_CUBIC)
                # 	cv2.imwrite(filename + ".letter" + str(x) + ".png", cropped_letter_resized)

                self.white_bg[y:y+h, x:x+w] = cropped_letter
                #seperate letters in case they are joined by a bottom frame border
                cv2.rectangle(self.white_bg, (x, y), (x + w, y + h), (255,255,255), 1)

                if self.debugEnabled:
                    cv2.imwrite(filename + ".letter." + str(i) + "." + str(x) + ".png", self.white_bg)

                #cv2.drawContours(masked, [c], -1, (255,255,255), -1)
        
        if self.debugEnabled:
            cv2.imwrite(filename + ".mask.png", self.masked)

        self.time_taken_by_extractLetters = time.time() - timeStart
        return letters

    def findRectsCase(self, img, filename):
        """This is the normal case when the letters are in the center of the plate
            and there is ample padding on each letter for contouring to do it's magic
        """

        timeStart = time.time()

        localImage = img.copy()
        localImage = cv2.bilateralFilter(localImage, 9,75,75)

        height,width = localImage.shape

        blockDim = min( height // 4, width // 4)
        if (blockDim % 2 != 1):
            blockDim  = blockDim+1

        rectsFound = 0

        thresh = cv2.adaptiveThreshold(localImage.copy(),255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,blockDim,0)
        #cv2.imwrite("filter.thresh.bininv.jpg",thresh)        
        edges = cv2.Canny(thresh,100,200)
        #cv2.imwrite("filter.edges.thresh.bininv.jpg",edges)
        rectsFound = rectsFound + self.findAndAppendContours(edges)
        

        #https://docs.scipy.org/doc/numpy-1.10.0/reference/generated/numpy.sort.html
        self.brects_sorted=np.array(self.brects_unsorted, dtype=self.dtype_letter_rect)
        self.brects_sorted=np.sort(self.brects_sorted, order=['x'])


        self.time_taken_by_findRectsNormalCase = self.time_taken_by_findRectsNormalCase + (time.time() - timeStart)

        return rectsFound, thresh


    def findRects(self, filename):
        """Returns a list of rects by
            finding contours in the provided image

            The function calls a series of functions each of which addresses
            a different occurring problem
        """

        # #add border, this is for images which have a letter at the edge which
        # # otherwise will not be detected by contours..read theory
        # self.plate = cv2.copyMakeBorder(self.plate,2,2,2,2,cv2.BORDER_CONSTANT,(255,255,255))
        # print("Plate dimensions: [{}]".format(self.plate.shape))

        #convert to gray scale
        imgray = cv2.cvtColor(self.plate, cv2.COLOR_BGR2GRAY)

        self._height, self._width = imgray.shape


        rects_round1, img_round1 = self.findRectsCase(imgray, filename)
        self.thresh = img_round1

        if self.debugEnabled:
            cv2.imwrite(filename + ".pre.thresh.png", self.thresh)

        height,width = self.thresh.shape
        mid = int(width/2)
        imColorDetect = self.thresh[0:height, mid-50 : mid+50]
        color_avg = self.detectColor(imColorDetect)

        if(color_avg < 130):
            #we got a white plate... invert it so letters ar ein black
            self.thresh = cv2.bitwise_not(self.thresh)

        if self.debugEnabled:
            cv2.imwrite(filename + ".final.thresh.png", self.thresh)

        return self.brects_sorted

    def overlayImageOnBlackCanvas(self, img, canvas_shape = (400,400,3)):

        h,w,c = img.shape

        computed_canvas_shape = canvas_shape
        resizeAtEnd = False

        if h>canvas_shape[0] or w>canvas_shape[1]:
            max_dim = max(h,w)
            computed_canvas_shape = (max_dim,max_dim,c)
            
            resizeAtEnd = True

        canvas = np.zeros(computed_canvas_shape).astype(np.uint8)

        insert_y = (computed_canvas_shape[0] - h) //2
        insert_x = (computed_canvas_shape[1] - w) //2
        
        canvas[insert_y: insert_y+h , insert_x:insert_x+w] = img

        if resizeAtEnd is True:
            canvas = resize(canvas, canvas_shape, preserve_range=True).astype(np.uint8)

        return canvas


    def printTimeStatistics(self):
        print("Time statistics:")
        print("[{}] self.time_taken_by_skewCorrection".format(self.time_taken_by_skewCorrection))
        print("[{}] self.time_taken_by_analyzeRects".format(self.time_taken_by_analyzeRects ))
        print("[{}] self.time_taken_by_breakupBoxesAndCalcWeights".format(self.time_taken_by_breakupBoxesAndCalcWeights ))
        print("[{}] self.time_taken_by_eliminateByCog".format(self.time_taken_by_eliminateByCog ))
        print("[{}] self.time_taken_by_eliminateByArea".format(self.time_taken_by_eliminateByArea ))
        print("[{}] self.time_taken_by_determineBlackOrWhite".format(self.time_taken_by_determineBlackOrWhite ))
        print("[{}] self.time_taken_by_findAndAppendContours".format(self.time_taken_by_findAndAppendContours ))
        print("[{}] self.time_taken_by_extractLetters".format(self.time_taken_by_extractLetters ))
        print("[{}] self.time_taken_by_findRectsNormalCase".format(self.time_taken_by_findRectsNormalCase ))
        
    #def getPlate(self, im, x,y,w,h, filename):
    def processPlate(self, plate, filename):

        try:
            originalPlate = np.expand_dims(cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY), axis=2)

            #crop only to lp
            self.plate = plate

            self.findRects(filename)
            if len(self.brects_sorted) == 0:
                return [],[]

            #print("Found [{}] rects.".format(len(self.brects_sorted)))

            #gather basic statistics
            self.analyzeRects(filename)
            if len(self.brects_sorted) == 0:
                return [],[]

            # eliminate by y deviation, important to call before calling next cog elimination
            self.eliminateByYDeviation(filename)
            if len(self.brects_sorted) == 0:
                return [], []

            #eliminate duplicates
            self.eliminateByCog(filename)
            if len(self.brects_sorted) == 0:
                return [],[]

            # eliminate by overlap, larger rects must go
            self.eliminateByOverlap()
            if len(self.brects_sorted) == 0:
                return [],[]

            self.eliminateByAvgHeight()
            if len(self.brects_sorted) == 0:
                return [],[]

            self.discoverToLeft()
            if len(self.brects_sorted) == 0:
                return [],[]

            self.discoverInMiddle()
            if len(self.brects_sorted) == 0:
                return [],[]

            self.discoverToRight()
            if len(self.brects_sorted) == 0:
                return [],[]

            numRects = len(self.brects_sorted)
            if numRects == 0:
                return [],[]

            oh, ow, oc = originalPlate.shape
            rois = np.empty((numRects,96,64,oc),np.uint8)
            ph, pw = 6,6
            
            for i in range(0, len(self.brects_sorted)):
                x,y,w,h,cogx,cogy,wr,area = self.brects_sorted[i]

                x_start = x
                y_start = y
                x_end = x + w
                y_end = y + h

                # print("xs:xe ys:ye {}:{} {}:{}".format(x_start, x_end, y_start, y_end),end=' ')

                #pad if possible
                if (x_start - pw) >= 0:
                    x_start -= pw
                else:
                    x_start = 0
                
                if (x_end + pw) < ow:
                    x_end += pw
                else:
                    x_end = ow

                if (y_start - ph) >= 0:
                    y_start -= ph
                else:
                    y_start = 0
                
                if (y_end + ph) < oh:
                    y_end += ph
                else:
                    y_end = oh

                sliced = originalPlate[y_start:y_end, x_start:x_end]

                sliced = self.overlayImageOnBlackCanvas(sliced, (96,64,oc)).astype(np.uint8)

                rois[i] = sliced
                #cv2.imwrite("roi.{}.jpg".format(i), sliced)

            return self.brects_sorted, rois
        except:
            print(traceback.format_exc())
            return self.masked