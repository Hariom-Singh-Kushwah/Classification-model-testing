import snap7
from snap7.util import *
from snap7.snap7types import *
import cv2
import tensorflow as tf
from tensorflow.keras import models
from tensorflow.keras.models import Sequential
import pickle
import numpy as np
import struct
from time import sleep
from picamera import PiCamera


# Plc communication
try:
    plc = snap7.client.Client()
    plc.connect("192.168.1.51",0,1)
except:
    print("Plc not connected.")

# bytearray to read,write to plc
bitarr_int=bytearray([0x00,0x00])  
read=bytearray([0x00])  

#Component list 
CATEGORIES = ['59_ac','59_c','61_ac','61_c','63_ac','63_c','66_ac','66_c','67_ac','67_c','none']

# Camera setings
camera = PiCamera()
camera.start_preview()
camera.resolution = (2592,1944)

counter = 1
# model loading 
model = tf.keras.models.load_model("/home/pi/data/model/BearingCap_v2.model")
while True:
  try:    
    reading = plc.db_read(35,8,1)  # read 1 byte from db address 35, staring from byte 8
    bit = snap7.util.get_bool(reading,0,6) 
    #print(bit)
    
    if bit == True:
        print('count:',counter)
        sleep(2)
        print('after_Sleep',bit)
        camera.capture('/home/pi/data/test.jpg')
        frame = cv2.imread('/home/pi/data/test.jpg')
        
        # ROI selection 
        var1 = frame[530:1480, 1880:2260]
        var2 = frame[90:450, 860:1750]
        var3 = frame[550:1450, 380:770]
        var4 = frame[1570:1970, 850:1780]
 
        # Frame Rotation according to training data
        var2 = cv2.rotate(var2, cv2.ROTATE_90_CLOCKWISE)
        var3 = cv2.rotate(var3, cv2.ROTATE_180)
        var4 = cv2.rotate(var4, cv2.ROTATE_180)
        var4 = cv2.rotate(var4, cv2.ROTATE_90_CLOCKWISE)

        # Saving ROI for classification
        cv2.imwrite("/home/pi/data/ROI0.jpg", var1)
        cv2.imwrite("/home/pi/data/ROI2.jpg", var2)
        cv2.imwrite("/home/pi/data/ROI4.jpg", var3)
        cv2.imwrite("/home/pi/data/ROI6.jpg", var4)

        count = 0
        com_num_list = []
        com_ori_list = []
        # Processing ROIs images
        for num in range(0,8,2):
            def prepare(filepath):
                IMG_SIZE = 100
                img_array = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
                new_array = cv2.resize(img_array, (IMG_SIZE, IMG_SIZE))
                return new_array.reshape(-1, IMG_SIZE, IMG_SIZE, 1)
            # Prediction fo ROIs
            prediction  = model.predict(prepare('/home/pi/data/ROI{}.jpg'.format(num)))
            print('Position',count+1)
            print(prediction)

            inds = []
            # from the prediction slecting max index value to know the component number
            for i in prediction[0]:
                inds.append(i)
            index = inds.index(max(inds))
            com = CATEGORIES[index]
            fourth_com = com[:2]
            if fourth_com == '59':
                fourth_com = 2
            if fourth_com == '61':
                fourth_com = 7
            if fourth_com == '63':
                fourth_com = 1
            if fourth_com == '66':
                fourth_com = 4
            if fourth_com == '67':
                fourth_com = 5
            if fourth_com == 'no':
                fourth_com = 15

            # Updating the classified component number to PLC
            print(fourth_com)
            snap7.util.set_int(bitarr_int,0,fourth_com) #bitarr is the byte array here, 0 is the byte address, from where the value is to set and 6 is the value
            plc.db_write(35,num,bitarr_int)
            fourth_ori = com[3:]
            if fourth_ori == 'c':
                fourth_ori = 1
            else:
                fourth_ori = 0

            snap7.util.set_bool(read,0,count,fourth_ori)
            plc.db_write(35,8,read)
            
            count += 1
            com_num_list.append(fourth_com)
            com_ori_list.append(fourth_ori)

        # Updating classification results to plc for all position
        if com_num_list[0] !=  15 and com_num_list[1] != 15 and com_num_list[2] != 15 and com_num_list != 15:
            if com_num_list[0] == com_num_list[1] == com_num_list[2] == com_num_list[3]:
                if com_ori_list[0] == 1 and com_ori_list[1] == 1 and com_ori_list[2] == 1 and com_ori_list[3] == 1:
                    snap7.util.set_bool(read,0,4,1)
                    plc.db_write(35,8,read)
                else:
                    snap7.util.set_bool(read,0,4,0)
                    plc.db_write(35,8,read)
            else:
                snap7.util.set_bool(read,0,4,0)
                plc.db_write(35,8,read)
        else:
            snap7.util.set_bool(read,0,4,0)
            plc.db_write(35,8,read)
        #print('New cycle start')
        print('\n')
        counter += 1
  except:
    print("Error")

