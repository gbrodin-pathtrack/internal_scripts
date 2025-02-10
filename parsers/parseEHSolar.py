from datetime import timedelta
from parsers.parsePackedTime import parsePackedTime

def parseEHSolarLine(data, commonHeader, lineNum, outputArr):
    #convert ptTimePacked to python datetime
    startDateTime = parsePackedTime(data[:5])

    interval = data[5] + (data[6]<<8)

    vocArr = data[7::3]
    harvLArr = data[8::3]
    harvHArr = data[9::3]
    harvArr = harvLArr + (harvHArr << 8)

    solarValues = [{"line":lineNum,"time":0,"VOC":voc, "harvCount":harv} for voc, harv in zip(vocArr, harvArr)]

    timeStep = timedelta(seconds=interval)
    obsDatetime = startDateTime
    for obs in solarValues:
        obs["time"] = obsDatetime
        obsDatetime += timeStep

    outputArr.extend(solarValues)
