import pandas as pd
import numpy as np
from parsers.parseInt import parseUInt16, parseUInt32
from os import listdir
from os.path import isfile, join
import sys

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

    contactArr = []
    for lineNum, line in enumerate(byteLines):
        #only process contact lines
        if line[0] != 0xFD:
            continue

        length = line[1] + (line[2] << 8)
        index = 3
        while index < length:
            contactArr.append(
                {"lineNum":lineNum + LINE_OFFSET,
                 "tagID":parseUInt16(line[index:]),
                 "vbatt":line[index+2],
                 "secondsOfYear":(parseUInt32(line[index+3:]) & 0x7FFFFFFF) >> 6,
                 "RSSI":(line[index+7] & 0x7F) - (line[index+7] & 0x80) - line[index+8]}
            )
            index += 9

    df = pd.DataFrame(contactArr)

    if USE_PICKLE:
        df.to_pickle(fileName[:-4]+"_contacts.pkl")
    else:
        df.to_csv(fileName[:-4]+"_contacts.csv",index=False)



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
