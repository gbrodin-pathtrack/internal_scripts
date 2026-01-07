import datetime
import numpy as np
from parsers.parsePackedTime import parsePackedTime
from parsers.parserSettings import getSetting

MIN_CNR = 25

def convSatTime(svTime : int):
    if svTime < 200:
        return svTime/10
    return 20 + (svTime-200)

def parseObs(lineNum : int, data : np.ndarray, obsArr : list, satArr : list, sixSVTimes : bool) -> int:
    fixTime = parsePackedTime(data[:5])
    numImmersionBits = data[5]
    if numImmersionBits == 0xFF:
        numImmersionBits = 0
    immersionBytes = data[6:9]
    immersionString = "'"
    immersionIndex = 0
    while numImmersionBits != 0:
        byteBits = 8 if numImmersionBits > 8 else numImmersionBits
        immersionByte = immersionBytes[immersionIndex]
        for i in range(byteBits):
            if immersionByte & (0x1 << i) != 0:
                immersionString += "1"
            else:
                immersionString += "0"
        immersionIndex += 1
        numImmersionBits -= byteBits
    totalSV = data[9]
    vbatt = data[10]
    ttf = data[11]/getSetting("DIV_TTF")
    svTimes = []
    if sixSVTimes:
        index = 12
        for _ in range(6):
            svTimes.append(convSatTime(data[index]))
            index += 1
    else:
        svTimes.append(convSatTime(data[12]))
        index = 13
    startTime = fixTime - datetime.timedelta(seconds=ttf)
    obs = {"line":lineNum,"datetime":fixTime,"numSV":0,"numBadSV":0,"vbatt":vbatt,"TTF":ttf,"startDatetime":startTime,"immersion":immersionString}
    for i in range(len(svTimes)):
        obs["svTime_%d" % (i+1)] = svTimes[i]
    obsArr.append(obs)
    wantedSV = 0
    end = index + totalSV*5
    while index < end:
        sat = {}
        sat.update(obs)
        sat["ID"] = data[index]
        if data[index+1] >= MIN_CNR:
            wantedSV += 1
        sat["CNR"] = data[index+1]
        sat["codePhase"] = data[index+2] + (data[index + 3]<<8) + (data[index + 4]<<16)
        index += 5
        satArr.append(sat)

    obs["numSV"] = wantedSV
    obs["numBadSV"] = totalSV - wantedSV

    return end


def parseGPSLegring2026(data : np.ndarray, commonHeader : np.ndarray, lineNum : int, mixed : bool) -> dict[str, list]:
    if mixed:
        raise ValueError("No mixed implementation for GPS Immersion")

    obsArr = []
    satArr = []
    index = 0
    while index < len(data):
        index += parseObs(lineNum, data[index:], obsArr, satArr, commonHeader[0] == 0x9E)

    if len(satArr) > 0:
        return {"GPS_IM_Obs":obsArr,"GPS_SVs":satArr}
    else:
        return {"GPS_IM_Obs":obsArr}
