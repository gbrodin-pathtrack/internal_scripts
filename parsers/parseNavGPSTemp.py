from datetime import datetime, timedelta
import numpy as np
from parsers.parsePackedTime import parsePackedTime

def parseNavGPSTempLine(data : np.ndarray, commonHeader : np.ndarray, lineNum : int) -> dict[str, list]:
    outputArr = []
    rawObsArr = [data[i:i+8] for i in range(0, len(data), 8)]

    for rawObs in rawObsArr:
        obs = {"line":lineNum}
        obs["time"] = parsePackedTime(rawObs[:5])
        navMsg = False
        if rawObs[5] & 0x80 == 0x80:
            navMsg = True
        obs["navMsg"] = navMsg
        obs["numSV"] = rawObs[5] & 0x7F
        obs["vbat"] = rawObs[6]
        obs["ttf"] = rawObs[7]
        outputArr.append(obs)

    return{"GPS_NAV_Temp":outputArr}