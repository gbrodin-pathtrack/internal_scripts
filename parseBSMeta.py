import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join
import sys

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
    for lineNum, line in enumerate(byteLines):
        #skip old style lines or blank lines
        if line[0] < 0x10 or line[0] == 0xFF:
            continue
        signal = (line[2] & 0xE0) >> 5
        metaArr.append({"lineNum":lineNum + LINE_OFFSET,
                        "transmissionStart":bool(line[2] & 0x10),
                        "tagID":line[3] + (line[4]<<8),
                        "fastMode":signal > 1,
                        "RSSI":SIGNAL_STRENGTH[signal]
                        })
    
    df = pd.DataFrame(metaArr)

    if USE_PICKLE:
        df.to_pickle(fileName[:-4]+"_meta.pkl")
    else:
        df.to_csv(fileName[:-4]+"_meta.csv",index=False)



#if CLI given take arguments as list of files
if len(sys.argv) > 1:
    wantedFiles= sys.argv[1:]
#no command line args given, auto select all dat files in current directory
else:
    #Every file name in current directory that starts with "Obs" and ends with ".dat"
    wantedFiles = [f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.startswith("Obs") and f.endswith(".dat") and "BS" in f]

for fileName in wantedFiles:
    #only produce a combined file if there are more than 1 dat files
    parseBSDat(ROOT+fileName)