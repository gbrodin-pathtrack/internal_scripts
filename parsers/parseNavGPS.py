from datetime import datetime, timedelta
import numpy as np
from parsers.parsePackedTime import parsePackedTime
from parsers.parseInt import parseInt32, parseUInt32, parseUInt16

OBS_TYPE_NAV = 0x80
OBS_TYPE_MEASX = 0x40
OBS_TYPE_START = 0x00

def parseMEASXObs(data : np.ndarray, obs : dict):
    #dont care about measx info for now
    return

def parseNAVObs(data : np.ndarray, obs : dict):
    nanos = parseInt32(data[:4])
    timediff = timedelta(microseconds=nanos/1000)
    obs["time"] += timediff
    obs["lat (deg)"] = parseInt32(data[4:8]) * 1e-7
    obs["long (deg)"] = parseInt32(data[8:12]) * 1e-7
    obs["elipsoidHeight (m)"] = parseInt32(data[12:16]) / 1000
    obs["pDOP"] = parseUInt16(data[16:18])
    obs["velN (m/s)"] = parseInt32(data[18:22]) / 1000
    obs["velE (m/s)"] = parseInt32(data[22:26]) / 1000
    obs["velD (m/s)"] = parseInt32(data[26:30]) / 1000
    obs["speedAcc (m/s)"] = parseUInt32(data[30:34]) / 1000


def parseObs(data : np.ndarray, obs : dict) -> int:
    #parse common data and create obs
    time = parsePackedTime(data[:5])
    numSVs = data[5] & 0x3F
    obs.update({"time":time,"type":0,"numSV":numSVs})

    #check data type and pass to relevant parser
    obsType = data[5] & 0xC0
    if obsType == OBS_TYPE_NAV:
        obs["type"] = "NAV"
        parseNAVObs(data[5:40], obs)
        return 40
    elif obsType == OBS_TYPE_MEASX:
        obs["type"] = "MEASX"
        parseMEASXObs(data[5:], obs)
        return 6 + (5*numSVs)
    elif obsType == OBS_TYPE_START:
        obs["type"] = "Start"
        obs["vbatt"] = data[6]
    else:
        obs["type"] = "Invalid"
        print("Obs with type 0x11 set")

    return 7

def parseNavGPSLine(data : np.ndarray, commonHeader : np.ndarray, lineNum : int) -> dict[str, list]:
    outputArr = []
    index = 0
    while index < len(data):
        obs = {"line":lineNum}
        index += parseObs(data[index:], obs)
        outputArr.append(obs)

    return{"GPS_NAV":outputArr}
