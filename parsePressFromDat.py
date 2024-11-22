import pandas as pd
import datetime
from os import listdir
from os.path import isfile, join

PRESS_HEADER = 0xC0
COMPRESSED_TIME = True

def decode16BitPress(value, sensor):
    if sensor == 0: #mini depth
        return value * 0.5
    elif sensor == 1: #mini alt
        return value * 0.02
    elif sensor == 2: #large com
        if value <= 55500:
            return value * 0.02
        if value > 55500:
            return 1100 + (value-55500)

def parseDatFile(fileName):
    with open(fileName,"r") as f:
        fileString = f.read()

    #split file into lines
    lines = fileString.split("\n")
    #get data lines and split into bytes
    byteLines = [line.split() for line in lines if line[:1].isdigit()]
    #convert each byte from a string to number
    byteLines = [[int(byte) for byte in byteLine] for byteLine in byteLines]

    pressByteLines = [line for line in byteLines if (line[0]&0xFE) == PRESS_HEADER]

    tags = {}

    for line in pressByteLines:
        uhfLine = line[0] % 2
        index = 1
        length = line[index] + (line[index+1]<<8)
        index += 2
        tagID = "logger"
        if uhfLine:
            tagID = str(line[index] + (line[index+1]<<8))
            index += 2
        
        if tagID not in tags.keys():
            tags[tagID] = []

        format = (line[index] & 0xF8) >> 3
        sensor = line[index] & 0x07
        index += 1    

        year = line[index] & 0x7F
        month = ((line[index] & 0x80) >> 7) + ((line[index+1] & 0x05) << 1)
        day = (line[index+1] & 0xF8) >> 3
        hour = line[index+2] & 0x1F
        minute = ((line[index+2] & 0xE0) >> 5) + ((line[index+3] & 0x07) << 3)
        second = ((line[index+3] & 0xF8) >> 3) + ((line[index+4] & 0x01) << 5)
        subsecond = (line[index+4] & 0xFE) >> 1
        index += 5

        startDatetime = datetime.datetime(year=2000+year, month=month, day=day, hour=hour, minute=minute, second=second)

        if format == 0:
            pressRaw = line[index] + (line[index+1]<<8)
            press = decode16BitPress(pressRaw, sensor)
            index += 2
            temp = ((line[index])*0.5)-40
            index += 1
            pressObs = {"datetime":startDatetime, "pressure":press,"temp":temp}
            tags[tagID].append(pressObs)
            
            while(index < length):
                offset = line[index] + (line[index+1]<<8)
                index += 2
                obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
                pressRaw = line[index] + (line[index+1]<<8)
                press = decode16BitPress(pressRaw, sensor)
                index += 2
                temp = ((line[index])*0.5)-40
                index += 1
                pressObs = {"datetime":obsDatetime, "pressure":press,"temp":temp}
                tags[tagID].append(pressObs)

        if format == 1:
            if sensor != 0:
                print("Format 2 with non mini depth, can't process")
                continue
            press = (line[index] * 40) + 1000
            index += 1
            pressObs = {"datetime":startDatetime, "pressure":press}
            tags[tagID].append(pressObs)
            
            while(index < length):
                offset = line[index] + (line[index+1] << 8)
                index += 2
                obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
                press = (line[index] * 40) + 1000
                index += 1
                
                pressObs = {"datetime":obsDatetime, "pressure":press}
                tags[tagID].append(pressObs)

        if format == 2:
            if sensor != 0:
                print("Format 3 with non mini depth, can't process")
                continue
            press = (line[index] * 40) + 1000
            index += 1
            temp = subsecond
            pressObs = {"datetime":startDatetime, "pressure":press,"temp":temp}
            tags[tagID].append(pressObs)
            
            while(index < length):
                offset = line[index] + ((line[index+1] & 0x07)<<8)
                temp = ((line[index+1]) & 0xF8)>>3
                index += 2
                obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
                press = (line[index] * 40) + 1000
                index += 1
                
                pressObs = {"datetime":obsDatetime, "pressure":press,"temp":temp}
                tags[tagID].append(pressObs)
        
        if format == 3:
            temp = ((line[index] + (subsecond << 8)) * 0.08) - 40
            index += 1
            pressObs = {"datetime":startDatetime,"temp":temp}
            tags[tagID].append(pressObs)
            
            while(index < length):
                offset = line[index] + ((line[index+1] & 0x07)<<8)
                temp = (((((line[index+1]) & 0xF8)<<5) + line[index+2]) * 0.08) - 40
                index += 3
                obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
                
                pressObs = {"datetime":obsDatetime,"temp":temp}
                tags[tagID].append(pressObs)
        
        if format == 4:
            interval = line[index]
            index += 1
            offset = 0           
            while(index < length):
                offset += interval
                obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
                pressRaw = line[index] + (line[index+1]<<8)
                press = decode16BitPress(pressRaw, sensor)
                index += 2
                pressObs = {"datetime":obsDatetime, "pressure":press}
                tags[tagID].append(pressObs)
    
    for tagID, pressObsArr in tags.items():
        df = pd.DataFrame(pressObsArr)
        df["timeDiff"] = df["datetime"].diff(1)

        tagIDfileStr = ""
        if tagID != "logger":
            tagIDfileStr = "_"+tagID+"_"
        df.to_csv(fileName[:-4]+tagIDfileStr+"_press.csv",index=False)

        print("*"*100)
        print(fileName)
        if "pressure" in df:
            print("Max pressure:",df["pressure"].max())
            print("Min pressure:",df["pressure"].min())
        if "temp" in df:
            print("Max temp:",df["temp"].max())
            print("Min temp:",df["temp"].min())
        print("Max time diff:",df["timeDiff"].max())
        print("Min time diff:",df["timeDiff"].min())
        print()


#run parseDatFile on every file in root directory that starts with "Obs" and ends with ".dat"
wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.startswith("Obs") and f.endswith(".dat")]
for file in wantedFiles:
    #only produce a combined file if there are more than 1 dat files
    parseDatFile(file)