from datetime import datetime, timedelta
import numpy as np
from parsers.parsePackedTime import parsePackedTime

#used to convert from range as stored in header
ACCEL_SCALES = [1, 16, 4, 8]

def parseImmersionAccel(data, commonHeader, outputArr):
    startDateTime = parsePackedTime(data[:5])
    
    accelScaleCode = data[6]
    accelScale = ACCEL_SCALES[accelScaleCode]

    interval = data[7]

    upperX = data[7::4]
    upperY = data[8::4]
    upperZ = data[9::4]
    lower = data[10::4]
    xArr = ((((upperX&0x7F) << 2) + ((lower&0x03)) - ((upperX&0x80)<<2))*accelScale)/512
    yArr = ((((upperY&0x7F) << 2) + ((lower&0x0C)>>2) - ((upperY&0x80)<<2))*accelScale)/512
    zArr = ((((upperZ&0x7F) << 2) + ((lower&0x30)>>4) - ((upperZ&0x80)<<2))*accelScale)/512
    validArr = ((lower&0x80)>>7).astype(bool)
    immersedArr = ((lower&0x40)>>6).astype(bool)
    magArr = np.sqrt(xArr**2 + yArr**2 + zArr**2)
    accelValues = [{"immersed":immersed,"accel_valid":accelValid,"x":x,"y":y,"z":z,"mag":mag} 
                   for immersed, accelValid, x, y, z, mag in zip(immersedArr, validArr, xArr, yArr, zArr, magArr)]

    timeStep = timedelta(seconds=interval)
    obsDatetime = startDateTime
    for obs in accelValues:
        obs["time"] = obsDatetime
        obsDatetime += timeStep

    outputArr.extend(accelValues)