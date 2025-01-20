from datetime import datetime, timedelta
import numpy as np
from parsers.parsePackedTime import parsePackedTime

#used to convert from range as stored in header
ACCEL_SCALES = [2, 16, 4, 8]

def parseImmersionAccel(data, commonHeader, outputArr):
    startDateTime = parsePackedTime(data[:5])
    
    accelScaleCode = (data[5] & 0x0C) >> 2
    accelScale = ACCEL_SCALES[accelScaleCode]

    scalarFlag = data[5] & 0x01

    interval = int(data[6])
    
    if scalarFlag == 1:
        lower = data[7::2]
        upper = data[8::2]
        magArr = (((upper<<6) + (lower&0x3F))*accelScale)/8192
        invalidArr = ((lower&0x80)>>7).astype(bool)
        immersedArr = ((lower&0x40)>>6).astype(bool)
        accelValues = [{"time":0,"immersed":immersed,"accel_valid":accelValid,"mag":mag} 
                    for immersed, accelValid, mag in zip(immersedArr, invalidArr, magArr)]
    else:
        lower = data[7::4]
        upperX = data[8::4]
        upperY = data[9::4]
        upperZ = data[10::4]
        xArr = ((((upperX&0x7F) << 2) + ((lower&0x03)) - ((upperX&0x80)<<2))*accelScale)/512
        yArr = ((((upperY&0x7F) << 2) + ((lower&0x0C)>>2) - ((upperY&0x80)<<2))*accelScale)/512
        zArr = ((((upperZ&0x7F) << 2) + ((lower&0x30)>>4) - ((upperZ&0x80)<<2))*accelScale)/512
        invalidArr = ((lower&0x80)>>7).astype(bool)
        immersedArr = ((lower&0x40)>>6).astype(bool)
        magArr = np.sqrt(xArr**2 + yArr**2 + zArr**2)
        accelValues = [{"time":0,"immersed":immersed,"accel_invalid":accelInvalid,"x":x,"y":y,"z":z,"mag":mag} 
                    for immersed, accelInvalid, x, y, z, mag in zip(immersedArr, invalidArr, xArr, yArr, zArr, magArr)]

    timeStep = timedelta(seconds=interval)
    obsDatetime = startDateTime
    for obs in accelValues:
        obs["time"] = obsDatetime
        obsDatetime += timeStep

    outputArr.extend(accelValues)