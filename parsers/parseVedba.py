from datetime import timedelta
import numpy as np
from parsers.parsePackedTime import parsePackedTime
from parsers.parseInt import parseUInt32

#used to convert from range as stored in header
ACCEL_SCALES = [2, 16, 4, 8]

def parseVeDBALine(data : np.ndarray, commonHeader : np.ndarray, lineNum : int) -> dict[str, list]:
    startDateTime = parsePackedTime(data[:5])
    scaleDuration = parseUInt32(data[5:9])

    accelScaleCode = (scaleDuration & 0xC0000000) >> 30
    accelScale = ACCEL_SCALES[accelScaleCode]

    subsecondDuration = scaleDuration & 0x3FFFFFFF

    vedbaArr = (data[9:]*accelScale)/128

    vedbaValues = [{"line":lineNum,"time":0,"avgVeDBA":vedba} for vedba in vedbaArr]

    timeStep = timedelta(microseconds=15625*(subsecondDuration/len(vedbaValues)))
    obsDatetime = startDateTime
    for obs in vedbaValues:
        obs["time"] = obsDatetime
        obsDatetime += timeStep

    return {"VeDBA":vedbaValues}