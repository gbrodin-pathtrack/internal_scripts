from datetime import datetime, timedelta
import numpy as np
from parsers.parsePackedTime import parsePackedTime

#used to convert from range as stored in header
ACCEL_SCALES = [1, 16, 4, 8]

def parseAccelLine(data, commonHeader, outputArr):
    #take scale from common header
    accelScaleCode = (commonHeader[0] & 0x0C) >> 2
    accelScale = ACCEL_SCALES[accelScaleCode]

    #take scalar/vector flag from common header
    scalarFlag = (commonHeader[0] & 0x02) >> 1

    #convert ptTimePacked to python datetime
    startDateTime = parsePackedTime(data[:5])

    subsecondDuration = data[5] + (data[6] << 8)

    if scalarFlag == 1:
        lower = data[7::2]
        upper = data[8::2]
        magArr = (((lower>>2) + (upper<<6))*accelScale)/16384
        accelValues = [{"mag":mag} for mag in magArr]
    else:
        upperX = data[7::4]
        upperY = data[8::4]
        upperZ = data[9::4]
        lower = data[10::4]
        xArr = ((((upperX&0x7F) << 2) + ((lower&0xC0)>>6) - ((upperX&0x80)<<2))*accelScale)/512
        yArr = ((((upperY&0x7F) << 2) + ((lower&0x30)>>4) - ((upperY&0x80)<<2))*accelScale)/512
        zArr = ((((upperZ&0x7F) << 2) + ((lower&0x0C)>>2) - ((upperZ&0x80)<<2))*accelScale)/512
        magArr = np.sqrt(xArr**2 + yArr**2 + zArr**2)
        accelValues = [{"X":x,"Y":y,"Z":z,"mag":mag} for x, y, z, mag in zip(xArr, yArr, zArr, magArr)]

    timeStep = timedelta(microseconds=15625*(subsecondDuration/len(accelValues)))
    obsDatetime = startDateTime
    for obs in accelValues:
        obs["time"] = obsDatetime
        obsDatetime += timeStep

    outputArr.extend(accelValues)
    