import datetime
import numpy as np
from datetime import timedelta
from parsers.parsePackedTime import parsePackedTimeZeroSS
from parsers.parseInt import parseUInt16

#Data type x = (High res, temp)
DATA_TYPES = [(True,True),(False,False),(False,True),(True,False)]

def parsePressSingleSemiLine(data : np.ndarray, commonHeader : np.ndarray, lineNum : int, mixed : bool) -> dict[str, list]:
    #mixed and non mixed identical

    startTime = parsePackedTimeZeroSS(data[:5])
    dataType = (data[5] & 0xF0) >> 4
    interval = int(data[5] & 0x0F)

    highRes = DATA_TYPES[dataType][0]
    temp = DATA_TYPES[dataType][1]

    dataPointSize = 1 + (1 if highRes else 0) + (1 if temp else 0)

    timeStep = timedelta(seconds=interval)

    obsArr = []
    blockTimeOffset = 0
    index = 6
    #loop over blocks
    while index < len(data):
        #no block time offset for first block in line
        if index > 6:
            blockTimeOffset = parseUInt16(data[index:])
            index += 2
        numReadings = data[index]
        index += 1
        blockEnd = index + numReadings * dataPointSize
        obsTime = startTime + timedelta(seconds=blockTimeOffset)
        #loop data points in block
        while index < blockEnd:
            obs = {"line":lineNum,"datetime":obsTime, "numReadings":numReadings}
            if highRes:
                obs["press"] = parseUInt16(data[index:]) * 0.5
                index += 2
            else:
                obs["press"] = (data[index] * 40) + 1000
                index += 1
            if temp:
                obs["temp"] = (data[index] * 0.5) - 40
                index += 1
            obsTime += timeStep
            obsArr.append(obs)

    return {"PressSingleSemi":obsArr}
