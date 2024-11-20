import pandas as pd
import datetime
from os import listdir, remove
from os.path import isfile, join, exists

PRESS_HEADER = 0xC0
COMPRESSED_TIME = True

def parseDatFile(fileName):
    with open(fileName,"r") as f:
        fileString = f.read()

    #split file into lines
    lines = fileString.split("\n")
    #get data lines and split into bytes
    byteLines = [line.split() for line in lines if line[:1].isdigit()]
    #convert each byte from a string to number
    byteLines = [[int(byte) for byte in byteLine] for byteLine in byteLines]

    pressByteLines = [line for line in byteLines if line[0] == PRESS_HEADER]

    pressObsArr = []
    lengths = []

    for line in pressByteLines:
        length = line[1] + (line[2]<<8)
        format = line[3]
        index = 4
        if COMPRESSED_TIME:
            year = line[index] & 0x7F
            month = ((line[index] & 0x80) >> 7) + ((line[index+1] & 0x05) << 1)
            day = (line[index+1] & 0xF8) >> 3
            hour = line[index+2] & 0x1F
            minute = ((line[index+2] & 0xE0) >> 5) + ((line[index+3] & 0x07) << 3)
            second = ((line[index+3] & 0xF8) >> 3) + ((line[index+4] & 0x01) << 5)
            subsecond = (line[index+4] & 0xFE) >> 1
            index += 5
        else:
            year = line[index]
            month = line[index+1]
            day = line[index+2]
            hour = line[index+3]
            minute = line[index+4]
            second = line[index+5]
            index += 6

        startDatetime = datetime.datetime(year=2000+year, month=month, day=day, hour=hour, minute=minute, second=second)

        if format == 0:
            press = (line[index] + (line[index+1]<<8))*0.5
            index += 2
            temp = ((line[index])*0.5)-40
            index += 1
            pressObs = {"datetime":startDatetime, "pressure":press,"temp":temp}
            pressObsArr.append(pressObs)
            
            while(index < length):
                offset = line[index] + (line[index+1]<<8)
                index += 2
                obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
                press = (line[index] + (line[index+1]<<8))*0.5
                index += 2
                temp = ((line[index])*0.5)-40
                index += 1
                pressObs = {"datetime":obsDatetime, "pressure":press,"temp":temp}
                pressObsArr.append(pressObs)

        if format == 16:
            press = (line[index] * 40) + 1000
            index += 1
            temp = subsecond
            pressObs = {"datetime":startDatetime, "pressure":press,"temp":temp}
            pressObsArr.append(pressObs)
            
            while(index < length):
                offset = line[index] + ((line[index+1] & 0x07)<<8)
                temp = ((line[index+1]) & 0xF8)>>3
                index += 2
                obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
                press = (line[index] * 40) + 1000
                index += 1
                
                pressObs = {"datetime":obsDatetime, "pressure":press,"temp":temp}
                pressObsArr.append(pressObs)

    df = pd.DataFrame(pressObsArr)
    df["timeDiff"] = df["datetime"].diff(1)

    print("*"*100)
    print(fileName)
    print("Max pressure:",df["pressure"].max())
    print("Min pressure:",df["pressure"].min())
    print("Max temp:",df["temp"].max())
    print("Min temp:",df["temp"].min())
    print("Max temp:",df["timeDiff"].max())
    print("Min temp:",df["timeDiff"].min())
    print()


#run parseDatFile on every file in root directory that starts with "Obs" and ends with ".dat"
wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.startswith("Obs") and f.endswith(".dat")]
for file in wantedFiles:
    #only produce a combined file if there are more than 1 dat files
    parseDatFile(file)