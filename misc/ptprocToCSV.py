import sys
from os import listdir
from os.path import isfile, join
from datetime import datetime, timedelta
import struct

ROOT = "./"

def convertPtproc(fileName : str):
    with open(fileName, mode="rb") as ptproc, open(fileName+".csv", mode="w") as csv:
        header = ptproc.read(8).decode("utf-8")
        if header != "PTPROC-1":
            print(fileName," - invalid header")
            return
        csv.write("satTime,processedTime,lat,lon,height,residual,battery,numSV,deltaT,clockOffset\n")

        while(True):
            satDict = {}

            firstBytes = ptproc.read(8)
            if len(firstBytes) != 8:
                break

            satDict["satTime"] = datetime(1, 1, 1) + timedelta(microseconds = (struct.unpack('Q', firstBytes)[0] & 0x3FFFFFFFFFFFFFFF) // 10)

            satDict["processedTime"] = datetime(1, 1, 1) + timedelta(microseconds = (struct.unpack('Q', ptproc.read(8))[0] & 0x3FFFFFFFFFFFFFFF) // 10)
            satDict["lat"] = struct.unpack('d', ptproc.read(8))[0]
            satDict["lon"] = struct.unpack('d', ptproc.read(8))[0]
            satDict["height"] = struct.unpack('d', ptproc.read(8))[0]
            satDict["residual"] = struct.unpack('d', ptproc.read(8))[0]
            satDict["battery"] = struct.unpack('d', ptproc.read(8))[0]
            satDict["numSV"] = struct.unpack('i', ptproc.read(4))[0]

            while(True):
                a = 0

                param = struct.unpack('H', ptproc.read(2))[0]
                length = struct.unpack('H', ptproc.read(2))[0]

                if param == 0: #end
                    break

                if param == 1 and length == 8:
                    satDict["deltaT"] = struct.unpack('d', ptproc.read(8))[0]

                elif param == 2 and length == 8:
                    satDict["clockOffset"] = struct.unpack('d', ptproc.read(8))[0]

                else:
                    ptproc.read(length)
                    print(fileName,"unknown param")

                b = 0

            csv.write(f'{satDict.get("satTime")},{satDict.get("processedTime")},{satDict.get("lat")},{satDict.get("lon")},{satDict.get("height")},{satDict.get("residual")},{satDict.get("battery")},{satDict.get("numSV")},{satDict.get("deltaT")},{satDict.get("clockOffset")}\n')

args = sys.argv[1:]

passedFiles = []
passedArgs = []
for arg in args:
    if arg.startswith("-"):
        passedArgs.append(arg.strip("-").lower())
    else:
        passedFiles.append(arg)

if len(passedArgs) > 0:
    print("Unrecongised arguments:",passedArgs)

#if CLI given take arguments as list of files
if len(passedFiles) > 0:
    wantedFiles = passedFiles
#no command line args given, auto select all dat files in current directory
else:
    #Every file name in current directory that starts with "Obs" and ends with ".dat"
    wantedFiles = [ROOT + f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.endswith(".ptproc")]

for fileName in wantedFiles:
    #only produce a combined file if there are more than 1 dat files
    convertPtproc(fileName)
