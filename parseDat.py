import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join
import sys
import time

from parsers.parseGPS import parseGPSLine
from parsers.parsePressSingle import parsePressSingleLine
from parsers.parseAccel import parseAccelLine
from parsers.parseImmersionAccel import parseImmersionAccelLine
from parsers.parseEHSolar import parseEHSolarLine
from parsers.parseNavGPSTemp import parseNavGPSTempLine
from parsers.parseNavGPS import parseNavGPSLine

USE_PICKLE = False

#add headers here without the UHF bit set, UHF bit will be extracted and handled the same for all header types
HEADERS = {0x90:parseGPSLine,
           0x98:parseNavGPSLine,
           0xC0:parsePressSingleLine,
           0xA0:parseAccelLine,
           0xA2:parseAccelLine,
           0xA4:parseAccelLine,
           0xA6:parseAccelLine,
           0xA8:parseAccelLine,
           0xAA:parseAccelLine,
           0xAC:parseAccelLine,
           0xAE:parseAccelLine,
           0xD2:parseImmersionAccelLine,
           0xE0:parseEHSolarLine
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

    for lineNum, line in enumerate(byteLines):
        #extract data type and UHF flag from common header
        dataType = line[0] & 0xFE
        uhfType = line[0] & 0x1

        #extract length from common header
        length = line[1] + (line[2]<<8)

        #extract tag ID if applicable from common header
        tagID = "logger"
        dataStart = 3
        if uhfType == 1:
            tagID = "Tag"+str(line[3] + (line[4]<<8))
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
        
        #get handler function from data type byte
        dataTypeHandler = HEADERS[dataType]

        #slice data and common header to be passed
        data = line[dataStart:length]
        commonHeader = line[:dataStart]
        
        #pass data, header and line num to handler function
        parsedDataTypes = dataTypeHandler(data, commonHeader, lineNum)
        
        #unpack returned data
        for dataTypeStr, parsedData in parsedDataTypes.items():
            if dataTypeStr not in tags[tagID].keys():
                tags[tagID][dataTypeStr] = []
            tags[tagID][dataTypeStr].extend(parsedData)

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

#if CLI given take arguments as list of files
if len(sys.argv) > 1:
    wantedFiles= sys.argv[1:]
#no command line args given, auto select all dat files in current directory
else:
    #Every file name in current directory that starts with "Obs" and ends with ".dat"
    wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.startswith("Obs") and f.endswith(".dat")]

for fileName in wantedFiles:
    #only produce a combined file if there are more than 1 dat files
    parseDatFile(fileName)
