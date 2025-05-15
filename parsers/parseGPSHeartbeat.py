from datetime import datetime, timedelta
import numpy as np
from parsers.parsePackedTime import parsePackedTime
from parsers.parseInt import parseInt32, parseUInt32, parseUInt16

OBS_TYPE_MEASX      = 0
OBS_TYPE_MEASX_TR   = 1
OBS_TYPE_START      = 2
OBS_TYPE_MEASX_F    = 3
OBS_TYPE_NAV        = 4
OBS_TYPE_HB1        = 5
OBS_TYPE_HB2        = 6
OBS_TYPE_HBN        = 7

OBS_STR = {OBS_TYPE_MEASX:"MEASX",
           OBS_TYPE_MEASX_TR:"MEASX Time Reset",
           OBS_TYPE_START:"Start Indicator",
           OBS_TYPE_MEASX_F:"MEASX Fill",
           OBS_TYPE_NAV:"NAV",
           OBS_TYPE_HB1:"Heartbeat(1)",
           OBS_TYPE_HB2:"Heartbeat(2)",
           OBS_TYPE_HBN:"Heartbeat(n)"}

HB1_STR = {0:"Battery Report",
           1:"GPS UART Fail"}

HB2_STR = {0:"Reset Report"}

HBN_STR = {}

def parseMEASXObs(data : np.ndarray, obs : dict, satArr : list[dict]):
    index = 0
    while index < len(data):
        sat = {}
        sat.update(obs)
        sat["ID"] = data[index]
        sat["CNR"] = data[index+1]
        sat["codePhase"] = data[index+2] + (data[index + 3]<<8) + (data[index + 4]<<16)
        index += 5
        satArr.append(sat)

def parseNAVObs(data : np.ndarray, obs : dict):
    nanos = parseInt32(data[:4])
    timediff = timedelta(microseconds=nanos/1000)
    obs["datetime"] += timediff
    obs["lat"] = parseInt32(data[4:8]) * 1e-7
    obs["long"] = parseInt32(data[8:12]) * 1e-7
    obs["elipsoidHeight"] = parseInt32(data[12:16]) / 1000
    obs["pDOP"] = parseUInt16(data[16:18]) * 0.01
    velN =  parseInt32(data[18:22])
    obs["velN"] = velN / 1000
    velE = parseInt32(data[22:26]) 
    obs["velE"] = velE / 1000
    velD = parseInt32(data[26:30])
    obs["velD"] = velD / 1000
    obs["speedAcc"] = parseUInt32(data[30:34]) / 1000
    obs["vel2D"] = np.sqrt(velN**2 + velE**2) / 1000
    obs["vel3D"] = np.sqrt(velN**2 + velE**2 + velD**2) / 1000


def parseObs(data : np.ndarray, output : dict[str, list], lineNum) -> int:
    #parse common data and create obs
    time = parsePackedTime(data[:5])

    satArr = []

    obsType = (data[5] & 0xE0) >> 5
    numSVs = data[5] & 0x1F

    obs = {"line":lineNum,"datetime":time,"type":OBS_STR[obsType]}

    size = 6

    if obsType < OBS_TYPE_HB1:
        obs["numSVs"] = numSVs

    if obsType == OBS_TYPE_MEASX or obsType == OBS_TYPE_MEASX_TR or obsType == OBS_TYPE_MEASX_F:
        if obsType != OBS_TYPE_MEASX_F:
            obs["vbatt"] = data[6]
            obs["TTF"] = data[7]/10
            obs["startDatetime"] = obs["datetime"] - timedelta(seconds=obs["TTF"])
            size += 2
        parseMEASXObs(data[size:size+5*numSVs], obs, satArr)
        size += 5*numSVs
    elif obsType == OBS_TYPE_START:
        obs["vbatt"] = data[6]
        size += 1
    elif obsType == OBS_TYPE_NAV:
        parseNAVObs(data[6:40], obs)
        size += 34
    elif obsType == OBS_TYPE_HB1:
        if numSVs in HB1_STR.keys():
            obs["HBType"] = HB1_STR[numSVs]
        else:
            obs["HBType"] = "Unknown (%d)" % numSVs
        size += 1
    elif obsType == OBS_TYPE_HB2:
        if numSVs in HB2_STR.keys():
            obs["HBType"] = HB2_STR[numSVs]
        else:
            obs["HBType"] = "Unknown (%d)" % numSVs
        size += 2
    elif obsType == OBS_TYPE_HBN:
        if numSVs in HBN_STR.keys():
            obs["HBType"] = HBN_STR[numSVs]
        else:
            obs["HBType"] = "Unknown (%d)" % numSVs
        size += 1 + data[6]

    if obsType <= OBS_TYPE_MEASX_TR:
        output["GPS_Obs"].append(obs)
    elif obsType <= OBS_TYPE_NAV:
        output["GPS_Nav"].append(obs)
    else:
        obs["HBData"] = " ".join(np.char.mod('%d', data[6:size]))
        output["Heartbeat"].append(obs)

    if satArr:
        output["GPS_SVs"].extend(satArr)

    return size

def parseGPSHeartbeatLine(data : np.ndarray, commonHeader : np.ndarray, lineNum : int) -> dict[str, list]:
    output = {"GPS_Obs":[],"GPS_SVs":[],"GPS_Nav":[],"Heartbeat":[]}
    index = 0
    while index < len(data):
        index += parseObs(data[index:], output, lineNum)

    for key in list(output.keys()):
        if not output[key]:
            del output[key]

    return output
