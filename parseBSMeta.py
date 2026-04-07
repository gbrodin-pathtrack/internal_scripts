import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join
import sys
from datetime import datetime

SIGNAL_STRENGTH = {0: "'-inf..-100", 1:"'-99..inf", 2:"'-inf..-90", 3:"'-89..-80", 4:"'-79..-70", 5:"'-69..-60", 6:"'-59..-50", 7:"'-49..inf"}

LINE_OFFSET = 6

USE_PICKLE = False

ROOT = "./"

def parseBSDat(fileName):
    with open(fileName, "r") as f:
        byteLines = [
            np.array([int(byte) for byte in line.split()])
            for line in f
            if line[:1].isdigit()
        ]

    metaArr = []
    testArr = []
    for lineNum, line in enumerate(byteLines):
        #skip old style lines or debug lines, handle 0xFB debug lines
        if line[0] < 0x10 or (line[0] >= 0xF0 and line[0] != 0xFB):
            continue
        signal = (line[2] & 0xE0) >> 5
        start = bool(line[2] & 0x10)
        tagID = line[3] + (line[4]<<8)
        fastMode = signal > 1
        rssi = SIGNAL_STRENGTH[signal]

        if line[0] == 0xFB:
            timestamp = datetime(year=line[5]+2000, month=line[6], day=line[7], hour=line[8], minute=line[9], second=line[10])
            testArr.append({"lineNum":lineNum + LINE_OFFSET,
                            "datetime":timestamp,
                            "count":line[11],
                            "transmissionStart":start,
                            "tagID":tagID,
                            "fastMode":fastMode,
                            "RSSI":rssi
                            })
        else:
            metaArr.append({"lineNum":lineNum + LINE_OFFSET,
                            "transmissionStart":start,
                            "tagID":tagID,
                            "fastMode":fastMode,
                            "RSSI":rssi
                            })
    
    if len(metaArr) > 0:
        metaDF = pd.DataFrame(metaArr)

        if USE_PICKLE:
            metaDF.to_pickle(fileName[:-4]+"_meta.pkl")
        else:
            metaDF.to_csv(fileName[:-4]+"_meta.csv",index=False)

    if len(testArr) > 0:
        testDF = pd.DataFrame(testArr)

        if USE_PICKLE:
            testDF.to_pickle(fileName[:-4]+"_test.pkl")
        else:
            testDF.insert(loc=testDF.columns.get_loc("datetime")+1,column="time",value=testDF["datetime"].dt.round("1s"))
            testDF["time"] = testDF["time"].dt.time
            testDF.insert(loc=testDF.columns.get_loc("datetime")+1,column="date",value=testDF["datetime"].dt.date)
            testDF.to_csv(fileName[:-4]+"_test.csv",index=False)



#if CLI given take arguments as list of files
if len(sys.argv) > 1:
    wantedFiles= sys.argv[1:]
#no command line args given, auto select all dat files in current directory
else:
    #Every file name in current directory that starts with "Obs" and ends with ".dat"
    wantedFiles = [ROOT + f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.startswith("Obs") and f.endswith(".dat") and "BS" in f]

for fileName in wantedFiles:
    #only produce a combined file if there are more than 1 dat files
    parseBSDat(fileName)
