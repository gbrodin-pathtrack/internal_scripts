from datetime import timedelta
import numpy as np
from parsers.parsePackedTime import parsePackedTime, parsePackedTimeZeroSS
from parsers.parseInt import parseUInt16

def parseEHSolarLine(data : np.ndarray, commonHeader : np.ndarray, lineNum : int) -> dict[str, list]:
    #convert ptTimePacked to python datetime
    startDateTime = parsePackedTimeZeroSS(data[:5])

    interval = parseUInt16(data[5:7])

    vocArr = (data[7::3]) * 0.01
    harvArr = data[8::3] + (data[9::3] << 8)

    solarValues = [{"line":lineNum,"datetime":0,"VOC":voc, "harvCount":harv} for voc, harv in zip(vocArr, harvArr)]

    timeStep = timedelta(seconds=interval)
    obsDatetime = startDateTime
    for obs in solarValues:
        obs["datetime"] = obsDatetime
        obsDatetime += timeStep

    return {"EHSolar":solarValues}
