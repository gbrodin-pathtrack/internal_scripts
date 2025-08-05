from os import listdir
from os.path import isfile, join
import pandas as pd
from datetime import datetime, timedelta

USE_PICKLE = True

DIV_TTF_10 = False

def parseRawFile(fileName):
    with open(fileName, "r") as f:
        lines = f.readlines()
        lines = [line.replace(',','.').split() for line in lines[5:]]
    
    tagID = int(fileName[-9:-4])

    satArr = []
    for line in lines:
        #lineSatArr = [{"ID":0}]
        lineSatArr = [{}]
        obs = {}
        time = datetime(year=int(line[0]),month=1, day=1)
        time += timedelta(days=int(line[1])-1, seconds=int(float(line[2])))
        obs["tagID"] = tagID
        obs["datetime"] = time
        obs["vbatt"] = float(line[3])
        obs["TTF"] = int(line[4]) / (10 if DIV_TTF_10 else 1)
        obs["startDatetime"] = obs["datetime"] - timedelta(seconds=obs["TTF"])
        numSV = int(line[5])
        obs["numSV"] = numSV
        obs["numGPS"] = numSV
        obs["numBeiDou"] = 0
        obs["numGalileo"] = 0
        for i in range(0,numSV*4,4):
            sat = {}
            sat["ID"] = int(line[6+i])
            sat["CNR"] = int(line[9+i])
            sat["codePhase"] = float(line[7+i])
            #lineSatArr.append(sat)

        for sat in lineSatArr:
            sat.update(obs)

        satArr.extend(lineSatArr)

    df = pd.DataFrame(satArr)

    if USE_PICKLE:
        df.to_pickle(fileName[:-4]+"_GPS_Obs.pkl")
    else:
        df.to_csv(fileName[:-4]+"_GPS_Obs.csv",index=False)

wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.startswith("Obs") and f.endswith(".raw")]

for fileName in wantedFiles:
    parseRawFile(fileName)