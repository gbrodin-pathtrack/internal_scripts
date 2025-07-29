from datetime import timedelta
import numpy as np
from parsers.parsePackedTime import parsePackedTimeZeroSS

def parseMagnetometerLine_Temp(data : np.ndarray, commonHeader : np.ndarray, lineNum : int, mixed : bool) -> dict[str, list]:
    if mixed:
        raise ValueError("No mixed implementation for magnetometer")

    #convert ptTimePacked to python datetime
    startDateTime = parsePackedTimeZeroSS(data[:5])

    interval = int(data[5])

    xArr = (data[6::6] + ((data[7::6]&0x7F)<<8) - ((data[7::6]&0x80)<<8)) * 1.5
    yArr = (data[8::6] + ((data[9::6]&0x7F)<<8) - ((data[9::6]&0x80)<<8)) * 1.5
    zArr = (data[10::6] + ((data[11::6]&0x7F)<<8) - ((data[11::6]&0x80)<<8)) * 1.5

    mArr = np.sqrt(xArr**2 + yArr**2 + zArr**2)

    magnetometerValues = [{"line":lineNum,"datetime":0,"X":x, "Y":y, "Z":z, "Magnitude":m} for x, y, z, m in zip(xArr, yArr, zArr, mArr)]

    timeStep = timedelta(seconds=interval)
    obsDatetime = startDateTime
    for obs in magnetometerValues:
        obs["datetime"] = obsDatetime
        obsDatetime += timeStep

    return {"Magnetometer":magnetometerValues}
