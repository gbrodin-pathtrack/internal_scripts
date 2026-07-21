from datetime import timedelta
import numpy as np
from parsers.parsePackedTime import parsePackedTime
from parsers.parseInt import parseUInt16

ACCEL_RATES = {0x80 : 1, 0x90: 12.5, 0xA0 : 25, 0xB0 : 50}

ACCEL_SCALES = [2, 16, 4, 8]

def parseMagAccelLine(data : np.ndarray, commonHeader : np.ndarray, lineNum : int, mixed : bool) -> dict[str, list]:
    if mixed:
        raise ValueError("No mixed implementation for mag accel")

    #convert ptTimePacked to python datetime
    startDateTime = parsePackedTime(data[:5])

    interval =  (data[6] * 125) / ACCEL_RATES[data[5] & 0xF0]

    accScale = ACCEL_SCALES[(data[5] & 0x0C) >> 2]

    magXArr = (data[7::10] + ((data[8::10]&0x7F)<<8) - ((data[8::10]&0x80)<<8)) * 1.5
    magYArr = (data[9::10] + ((data[10::10]&0x7F)<<8) - ((data[10::10]&0x80)<<8)) * 1.5
    magZArr = (data[11::10] + ((data[12::10]&0x7F)<<8) - ((data[12::10]&0x80)<<8)) * 1.5

    accUpperX = data[13::10]
    accUpperY = data[14::10]
    accUpperZ = data[15::10]
    accLower = data[16::10]
    accXArr = ((((accUpperX&0x7F) << 2) + ((accLower&0xC0)>>6) - ((accUpperX&0x80)<<2)) * accScale) / 512
    accYArr = ((((accUpperY&0x7F) << 2) + ((accLower&0x30)>>4) - ((accUpperY&0x80)<<2)) * accScale) / 512
    accZArr = ((((accUpperZ&0x7F) << 2) + ((accLower&0x0C)>>2) - ((accUpperZ&0x80)<<2)) * accScale) / 512

    #fill in datetime with 0 for now
    values = [{"line":lineNum,"datetime":0,"magX":magX, "magY":magY, "magZ":magZ, "accX":accX, "accY":accY, "accZ":accZ}
              for magX, magY, magZ, accX, accY, accZ in zip(magXArr, magYArr, magZArr, accXArr, accYArr, accZArr)]

    timeStep = timedelta(seconds=interval)
    obsDatetime = startDateTime
    for obs in values:
        obs["datetime"] = obsDatetime
        obsDatetime += timeStep

    return {"MagAcc":values}
