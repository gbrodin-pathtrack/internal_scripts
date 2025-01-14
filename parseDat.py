import pandas as pd
from os import listdir
from os.path import isfile, join

from parsers.parseGPS import parseGPSLine
from parsers.parsePressSingle import parsePressSingleLine

HEADERS = {0x90:("GPS",parseGPSLine),
           0xC0:("PressSingle",parsePressSingleLine)
           }

def parseDatFile(fileName):
    with open(fileName,"r") as f:
        fileString = f.read()

    #split file into lines
    lines = fileString.split("\n")
    #get data lines and split into bytes
    byteLines = [line.split() for line in lines if line[:1].isdigit()]
    #convert each byte from a string to number
    byteLines = [[int(byte) for byte in byteLine] for byteLine in byteLines]

    #empty dict for tag IDs
    tags = {}

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
        
        #pass line of data and reference to output array to handler function
        dataTypeHandler(data, tags[tagID][dataTypeStr])
    
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
            df.to_csv(fileName[:-4]+tagIDfileStr+"_"+dataType+".csv",index=False)

#run parseDatFile on every file in root directory that starts with "Obs" and ends with ".dat"
wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.startswith("Obs") and f.endswith(".dat")]
for fileName in wantedFiles:
    #only produce a combined file if there are more than 1 dat files
    parseDatFile(fileName)