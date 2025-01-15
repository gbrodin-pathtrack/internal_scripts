import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join

import time

from parsers.parseGPS import parseGPSLine
from parsers.parsePressSingle import parsePressSingleLine
from parsers.parseAccel import parseAccelLine

USE_PICKLE = True

HEADERS = {0x90:("GPS",parseGPSLine),
           0xC0:("PressSingle",parsePressSingleLine),
           0xA0:("Accel",parseAccelLine),
           0xA2:("Accel",parseAccelLine),
           0xA4:("Accel",parseAccelLine),
           0xA6:("Accel",parseAccelLine),
           0xA8:("Accel",parseAccelLine),
           0xAA:("Accel",parseAccelLine),
           0xAC:("Accel",parseAccelLine),
           0xAE:("Accel",parseAccelLine)
           }

def parseDatFile(fileName):
    print("Processing",fileName)
    start = time.time()
    #read every line from file, ignoring header lines and produce a list of np arrays of bytes
    with open(fileName, "r") as f:
        byteLines = [
            np.array([int(byte) for byte in line.split()])
            for line in f
            if line[:1].isdigit()
        ]

    end = time.time()
    print("Time reading and converting file",end-start)

    #empty dict for tag IDs
    tags = {}

    start = time.time()

    for line in byteLines:
        #extract data type and UHF flag from common header
        dataType = line[0] & 0xFE
        uhfType = line[0] & 0x1

        #extract length from common header
        length = line[1] + (line[2]<<8)

        #extract tag ID if applicable from common header
        tagID = "logger"
        dataStart = 3
        if uhfType == 1:
            tagID = str(line[3] + (line[4]<<8))
            dataStart = 5

        #create entry for tag ID if needed
        if tagID not in tags.keys():
            tags[tagID] = {}

        #if datatype not known, add line to list of unknowns and skip
        if dataType not in HEADERS.keys():
            if "Unknown" not in tags[tagID].keys():
                tags[tagID]["Unknown"] = []
            tags[tagID]["Unknown"].append(line)
            continue
        
        #create data type entry if needed
        dataTypeStr = HEADERS[dataType][0]
        dataTypeHandler = HEADERS[dataType][1]
        if dataTypeStr not in tags[tagID].keys():
            tags[tagID][dataTypeStr] = []

        #strip common header and invalid bytes
        data = line[dataStart:length]

        commonHeader = line[:dataStart]

        
        #pass line of data and reference to output array to handler function
        dataTypeHandler(data, commonHeader, tags[tagID][dataTypeStr])

    end = time.time()
    print("Time parsing lines",end-start)
    start = time.time()
    #generate output files for each tag for each data type
    for tagID, tagData in tags.items():
        for dataType, obsArr in tagData.items():
            tagIDfileStr = ""
            if tagID != "logger":
                tagIDfileStr = "_"+tagID

            #dont make CSV for unknown data types
            if dataType == "Unknown":
                with open(fileName[:-4]+tagIDfileStr+"_Unknown.txt","w") as f:
                    f.write("\n".join([" ".join(["%02X" % byte for byte in line]) for line in obsArr]))
                continue

            df = pd.DataFrame(obsArr)
            #df.to_csv(fileName[:-4]+tagIDfileStr+"_"+dataType+".csv",index=False)
            if USE_PICKLE:
                df.to_pickle(fileName[:-4]+tagIDfileStr+"_"+dataType+".pkl")
            else:
                df.to_csv(fileName[:-4]+tagIDfileStr+"_"+dataType+".csv",index=False)

    end = time.time()
    print("Time writing output files",end-start)
    print()

#run parseDatFile on every file in root directory that starts with "Obs" and ends with ".dat"
wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.startswith("Obs") and f.endswith(".dat")]
for fileName in wantedFiles:
    #only produce a combined file if there are more than 1 dat files
    parseDatFile(fileName)