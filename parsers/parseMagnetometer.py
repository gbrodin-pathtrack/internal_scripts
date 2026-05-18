from datetime import timedelta
import numpy as np
from parsers.parsePackedTime import parsePackedTimeZeroSS
from parsers.parseInt import parseUInt16

def parseMagnetometerLine(data : np.ndarray, commonHeader : np.ndarray, lineNum : int, mixed : bool) -> dict[str, list]:
    if mixed:
        raise ValueError("No mixed implementation for magnetometer")

    #convert ptTimePacked to python datetime
    startDateTime = parsePackedTimeZeroSS(data[:5])
    startSS = int((data[4] & 0xFE) >> 1)

    interval = parseUInt16(data[5:7])

    ssArr = data[7::7]
    xArr = (data[8::7] + ((data[9::7]&0x7F)<<8) - ((data[9::7]&0x80)<<8)) * 1.5
    yArr = (data[10::7] + ((data[11::7]&0x7F)<<8) - ((data[11::7]&0x80)<<8)) * 1.5
    zArr = (data[12::7] + ((data[13::7]&0x7F)<<8) - ((data[13::7]&0x80)<<8)) * 1.5

    #fill in datetime with subseconds for now
    magnetometerValues = [{"line":lineNum,"datetime":int(ss),"X":x, "Y":y, "Z":z} for ss, x, y, z in zip(ssArr, xArr, yArr, zArr)]

    if interval > 1000:
        timeStep = timedelta(milliseconds=interval)
        obsDatetime = startDateTime
        for obs in magnetometerValues:
            obs["datetime"] = obsDatetime
            obsDatetime += timeStep
    else:
        obsDatetime = startDateTime
        lastSS = startSS
        for obs in magnetometerValues:
            if obs["datetime"] < lastSS:
                obsDatetime += timedelta(seconds=1)
            lastSS = obs["datetime"]
            obs["datetime"] = obsDatetime + timedelta(microseconds=15625*lastSS)

    return {"Magnetometer":magnetometerValues}
