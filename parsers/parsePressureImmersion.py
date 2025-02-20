from datetime import timedelta
import numpy as np
from parsers.parsePackedTime import parsePackedTime

def parsePressure(compressedPress):
    if compressedPress > 32000:
        return (1100 + (compressedPress-32000)*4)
    else:
        return 600 + (compressedPress/64)


def parsePressureImmersionLine(data : np.ndarray, commonHeader : np.ndarray, lineNum : int) -> dict[str, list]:
    startDateTime = parsePackedTime(data[:5])
    temp = (data[5]/2) - 40
    interval = int(data[6])

    lowerArr = data[7::2]
    upperArr = data[8::2]
    
    immersionArr = (upperArr&0x80).astype(bool)
    pressArr = np.vectorize(parsePressure)(((upperArr&0x7F)<<8) + lowerArr)

    outputArr = [{"line":lineNum,"time":0,"pressure":press,"immersed":immersion} for press, immersion in zip(pressArr, immersionArr)]

    outputArr[0]["temp"] = temp

    timeStep = timedelta(seconds=interval)
    obsDatetime = startDateTime
    for obs in outputArr:
        obs["time"] = obsDatetime
        obsDatetime += timeStep

    return {"Pressure_Immersion":outputArr}