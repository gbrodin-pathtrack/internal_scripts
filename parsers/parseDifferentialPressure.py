from datetime import timedelta
import numpy as np
from parsers.parsePackedTime import parsePackedTimeZeroSS
from parsers.parseInt import parseUInt16

def parsePressure(compressedPress):
    if compressedPress > 32000:
        return (1100 + (compressedPress-32000)*4)
    else:
        return 600 + (compressedPress/64)


def parseDifferentialPressureLine(data : np.ndarray, commonHeader : np.ndarray, lineNum : int, mixed : bool) -> dict[str, list]:
    if mixed:
        raise ValueError("No mixed implementation for differential pressure")

    #extract header info
    startDateTime = parsePackedTimeZeroSS(data[:5])
    temp = (data[5]/2) - 40
    interval = int(data[6])

    #start with invalid reference pressure
    ref = -1

    #create empty list for pressure values and whether they are from a reference or not (only needed for debug)
    pressArr = []
    refArr = []

    #loop over data
    index = 7
    while index < len(data):
        #check differential bit
        if data[index] & 0x01:
            if ref == -1:
                raise ValueError("Differential pressure reading before reference")
            #shift difference down and convert sign bit
            diffByte = data[index] >> 1
            diff = (diffByte & 0x3F) - (diffByte & 0x40)
            #add difference to reference before scale conversion (safe as differential readings will never cross between the split scales)
            ref += diff
            pressArr.append(parsePressure(ref))
            refArr.append(False)
            index += 1
        else:
            #shift reference reading down and store for future conversions
            ref = parseUInt16(data[index:index+2])>>1
            #convert reference and store to output data
            pressArr.append(parsePressure(ref))
            refArr.append(True)
            index += 2

    outputArr = [{"line":lineNum,"datetime":0,"pressure":press, "reference":ref} for press, ref in zip(pressArr, refArr)]

    outputArr[0]["temp"] = temp

    #fill in time stamp for each reading based on start time and interval
    timeStep = timedelta(seconds=interval)
    obsDatetime = startDateTime
    for obs in outputArr:
        obs["datetime"] = obsDatetime
        obsDatetime += timeStep

    return {"Differential_Pressure":outputArr}