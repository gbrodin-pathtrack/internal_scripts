import datetime
import numpy as np
from parsers.parsePackedTime import parsePackedTime

def parseObs(lineNum : int, data : np.ndarray, obsArr : list, satArr : list) -> int:
    fixTime = parsePackedTime(data[:5])
    numSV = data[5]
    vbatt = data[6]
    ttf = data[7]/10
    startTime = fixTime - datetime.timedelta(seconds=ttf)
    obs = {"line":lineNum,"datetime":fixTime,"numSV":numSV,"vbatt":vbatt,"TTF":ttf,"startDatetime":startTime}
    obsArr.append(obs)

    end = 8 + numSV*5
    index = 8
    while index < end:
        sat = {}
        sat.update(obs)
        sat["ID"] = data[index]
        sat["CNR"] = data[index+1]
        sat["codePhase"] = data[index+2] + (data[index + 3]<<8) + (data[index + 4]<<16)
        index += 5
        satArr.append(sat)

    return end


def parseGPSLine(data : np.ndarray, commonHeader : np.ndarray, lineNum : int) -> dict[str, list]:
    obsArr = []
    satArr = []
    index = 0
    while index < len(data):
        index += parseObs(lineNum, data[index:], obsArr, satArr)
    
    if len(satArr) > 0:
        return {"GPS_Obs":obsArr,"GPS_SVs":satArr}
    else:
        return {"GPS_Obs":obsArr}