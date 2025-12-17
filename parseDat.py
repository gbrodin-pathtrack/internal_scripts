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
from parsers.parseNavGPS import parseNavGPSLine
from parsers.parsePressureImmersion import parsePressureImmersionLine
from parsers.parseVedba import parseVeDBALine
from parsers.parsePressureSingleSemi import parsePressSingleSemiLine
from parsers.parseGPSHeartbeat import parseGPSHeartbeatLine
from parsers.parseMixed import parseMixedLine
from parsers.parseMagnetometer_Temp import parseMagnetometerLine_Temp
from parsers.parseDifferentialPressure import parseDifferentialPressureLine
from parsers.parseGPSImmersion import parseGPSImmersionLine
from parsers.parseImmersion import parseImmersionLine

USE_PICKLE = False

UNSCRAMBLE = False

ATTACH_ID = False

ROOT = "./"

#add headers here without the UHF bit set, UHF bit will be extracted and handled the same for all header types
HEADERS = {0x90:parseGPSLine,
           0x92:parseGPSHeartbeatLine,
           0x94:parseGPSLine,
           0x96:parseGPSHeartbeatLine,
           0x98:parseNavGPSLine,
           0x9C:parseGPSImmersionLine,
           0xA0:parseAccelLine,
           0xA2:parseAccelLine,
           0xA4:parseAccelLine,
           0xA6:parseAccelLine,
           0xA8:parseAccelLine,
           0xAA:parseAccelLine,
           0xAC:parseAccelLine,
           0xAE:parseAccelLine,
           0xB2:parsePressureImmersionLine,
           0xB4:parseDifferentialPressureLine,
           0xC0:parsePressSingleLine,
           0xC2:parsePressSingleSemiLine,
           0xD0:parseImmersionLine,
           0xD2:parseImmersionAccelLine,
           0xD6:parseMagnetometerLine_Temp,
           0xDA:parseVeDBALine,
           0xE0:parseEHSolarLine,
           0xE4:parseMixedLine,
           }

LINE_OFFSET = 6

def byteArrFromLine(line : str):
    if UNSCRAMBLE:
        words = line.split()
        return [int(words[(i*505) % 512]) for i in range(512)]
    else:
        return [int(byte) for byte in line.split()]

def parseDatFile(fileName : str):
    print("Processing",fileName)
    start = time.time()
    #read every line from file, ignoring header lines and produce a list of np arrays of bytes
    with open(fileName, "r") as f:
        byteLines = [
            np.array(byteArrFromLine(line))
            for line in f
            if line[:1].isdigit()
        ]

    end = time.time()
    print("Time reading and converting file",end-start)

    #empty dict for tag IDs
    tags: dict[str, dict[str, list]] = {}

    start = time.time()

    skipped = []

    tagIDidx = fileName.lower().find("tag")
    loggerTagID = 0
    if tagIDidx != -1:
        loggerTagID = int(fileName[tagIDidx+3:tagIDidx+8])

    for lineNum, line in enumerate(byteLines):
        #skip old type lines and debug/blank lines
        if line[0] < 0x10 or line[0] == 0xFF:
            continue

        #Add offset so line numbers match line numbers in dat file
        lineNum += LINE_OFFSET

        #extract data type and UHF flag from common header
        dataType = line[0] & 0xFE
        uhfType = line[0] & 0x1

        #extract length from common header
        length = line[1] + ((line[2]&0x0F)<<8)
        #lineInfo = line[2]&0xF0

        #extract tag ID if applicable from common header
        tagIDStr = "logger"
        dataStart = 3
        if uhfType == 1:
            tagIDStr = "Tag"+str(line[3] + (line[4]<<8))
            dataStart = 5

        #create entry for tag ID if needed
        if tagIDStr not in tags.keys():
            tags[tagIDStr] = {}

        #if datatype not known, add line to list of unknowns and skip
        if dataType not in HEADERS.keys():
            if "Unknown" not in tags[tagIDStr].keys():
                tags[tagIDStr]["Unknown"] = []
            tags[tagIDStr]["Unknown"].append(line)
            print("Skipping line",lineNum,"due to unknown data type")
            skipped.append(lineNum)
            continue
        
        #get handler function from data type byte
        dataTypeHandler = HEADERS[dataType]

        #slice data and common header to be passed
        data = line[dataStart:length]
        commonHeader = line[:dataStart]
        
        #pass data, header and line num to handler function
        try:
            parsedDataTypes = dataTypeHandler(data, commonHeader, lineNum, False)
        except ValueError as e:
            print("Skipping line",lineNum,"due to ValueError:")
            print(e)
            skipped.append(lineNum)
            continue
        except IndexError as e:
            print("Skipping line",lineNum,"due to IndexError")
            skipped.append(lineNum)
            continue
        
        #unpack returned data
        for dataTypeStr, parsedData in parsedDataTypes.items():
            if dataTypeStr not in tags[tagIDStr].keys():
                tags[tagIDStr][dataTypeStr] = []
            tags[tagIDStr][dataTypeStr].extend(parsedData)

    if(len(skipped)>0):
        print("Skipped lines:",skipped)

    end = time.time()
    print("Time parsing lines",end-start)
    start = time.time()
    #generate output files for each tag for each data type
    for tagIDStr, tagData in tags.items():
        for dataType, obsArr in tagData.items():
            tagIDfileStr = ""
            if tagIDStr != "logger":
                tagIDfileStr = "_"+tagIDStr

            #dont make CSV for unknown data types
            if dataType == "Unknown" or dataType == "Unknown_M":
                with open(fileName[:-4]+tagIDfileStr+"_"+dataType+".txt","w") as f:
                    f.write("\n".join([" ".join(["%02X" % byte for byte in line]) for line in obsArr]))
                continue

            df = pd.DataFrame(obsArr)

            if ATTACH_ID:
                if tagIDStr == "logger":
                    df["tagID"] = loggerTagID
                else:
                    df["tagID"] = int(tagIDStr[-5:])

            if USE_PICKLE:
                df.to_pickle(fileName[:-4]+tagIDfileStr+"_"+dataType+".pkl")
            else:
                if "datetime" in df.columns:
                    df.insert(loc=df.columns.get_loc("datetime")+1,column="time",value=df["datetime"].dt.round("1s"))
                    df["time"] = df["time"].dt.time
                    df.insert(loc=df.columns.get_loc("datetime")+1,column="date",value=df["datetime"].dt.date)
                df.to_csv(fileName[:-4]+tagIDfileStr+"_"+dataType+".csv",index=False)

    end = time.time()
    print("Time writing output files",end-start)
    print()

args = sys.argv[1:]

passedFiles = []
passedArgs = []
for arg in args:
    if arg.startswith("-"):
        passedArgs.append(arg.strip("-").lower())
    else:
        passedFiles.append(arg)

if "enc" in passedArgs:
    UNSCRAMBLE = True

if "id" in passedArgs:
    ATTACH_ID = True

if "pkl" in passedArgs:
    USE_PICKLE = True

#if CLI given take arguments as list of files
if len(passedFiles) > 0:
    wantedFiles = passedFiles
#no command line args given, auto select all dat files in current directory
else:
    #Every file name in current directory that starts with "Obs" and ends with ".dat"
    wantedFiles = [f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.startswith("Obs") and f.endswith(".dat")]

for fileName in wantedFiles:
    #only produce a combined file if there are more than 1 dat files
    parseDatFile(ROOT+fileName)
