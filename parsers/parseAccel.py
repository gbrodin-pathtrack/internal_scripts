from datetime import timedelta
import numpy as np
from parsers.parsePackedTime import parsePackedTime

#used to convert from range as stored in header
ACCEL_SCALES = [2, 16, 4, 8]

POST_CALCS = False

INTERESTING_G_OFFSET = 0.125

def parseAccelLine(data : np.ndarray, commonHeader : np.ndarray, lineNum : int) -> dict[str, list]:
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
        magArr = (((lower>>2) + (upper<<6))*accelScale)/8192
        accelValues = [{"line":lineNum,"datetime":0,"mag":mag} for mag in magArr]

        if POST_CALCS:
            interestingPoints = (magArr > (1 + INTERESTING_G_OFFSET)).sum() + (magArr < (1 - INTERESTING_G_OFFSET)).sum()

            summary = {"line":lineNum, "datetime":startDateTime, "interestingPoints":interestingPoints}
    else:
        upperX = data[7::4]
        upperY = data[8::4]
        upperZ = data[9::4]
        lower = data[10::4]
        xArr = ((((upperX&0x7F) << 2) + ((lower&0xC0)>>6) - ((upperX&0x80)<<2))*accelScale)/512
        yArr = ((((upperY&0x7F) << 2) + ((lower&0x30)>>4) - ((upperY&0x80)<<2))*accelScale)/512
        zArr = ((((upperZ&0x7F) << 2) + ((lower&0x0C)>>2) - ((upperZ&0x80)<<2))*accelScale)/512
        magArr = np.sqrt(xArr**2 + yArr**2 + zArr**2)
        if POST_CALCS:
            staticX = np.mean(xArr)
            staticY = np.mean(yArr)
            staticZ = np.mean(zArr)

            dynXArr = xArr - staticX
            dynYArr = yArr - staticY
            dynZArr = zArr - staticZ

            dynMagArr = np.sqrt(dynXArr**2 + dynYArr**2 + dynZArr**2)

            interestingPoints = (magArr > (1 + INTERESTING_G_OFFSET)).sum() + (magArr < (1 - INTERESTING_G_OFFSET)).sum()

            accelValues = [{"line":lineNum,"datetime":0,"X":x,"Y":y,"Z":z,"mag":mag,"dynX":dynX,"dynY":dynY,"dynZ":dynZ,"dynMag":dynMag} \
                           for x, y, z, mag, dynX, dynY, dynZ, dynMag in zip(xArr, yArr, zArr, magArr, dynXArr, dynYArr, dynZArr, dynMagArr)]
            
            summary = {"line":lineNum, "datetime":startDateTime, "staticX":staticX, "staticY":staticY, "staticZ":staticZ, \
                       "dynMagSum":np.sum(dynMagArr), "dynMagAvg":np.mean(dynMagArr), "interestingPoints":interestingPoints}
        else:
            accelValues = [{"line":lineNum,"datetime":0,"X":x,"Y":y,"Z":z,"mag":mag} for x, y, z, mag in zip(xArr, yArr, zArr, magArr)]

    timeStep = timedelta(microseconds=15625*(subsecondDuration/len(accelValues)))
    obsDatetime = startDateTime
    for obs in accelValues:
        obs["datetime"] = obsDatetime
        obsDatetime += timeStep
    if POST_CALCS:
        return {"Accel":accelValues,"AccelSummary":[summary]}
    else:
        return {"Accel":accelValues}
    