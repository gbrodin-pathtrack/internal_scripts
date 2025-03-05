from os import listdir
from os.path import isfile, join
import pandas as pd
from datetime import datetime, timedelta

USE_PICKLE = True

def parseRawFile(fileName):
    with open(fileName, "r") as f:
        lines = f.readlines()
        lines = [line.split() for line in lines[5:]]
    
    tagID = int(fileName[-9:-4])

    obsArr = []
    for line in lines:
        obs = {}
        time = datetime(year=int(line[0]),month=1, day=1)
        time += timedelta(days=int(line[1])-1, seconds=int(float(line[2])))
        obs["tagID"] = tagID
        obs["fixTime"] = time
        obs["TTF"] = int(line[4])
        obs["numSV"] = int(line[5])
        obsArr.append(obs)

    df = pd.DataFrame(obsArr)

    if USE_PICKLE:
        df.to_pickle(fileName[:-4]+"_GPS.pkl")
    else:
        df.to_csv(fileName[:-4]+"_GPS.csv",index=False)

wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.startswith("Obs") and f.endswith(".raw")]

for fileName in wantedFiles:
    parseRawFile(fileName)