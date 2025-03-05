from os import listdir
from os.path import isfile, join
import pandas as pd
from datetime import datetime, timedelta

USE_PICKLE = True

def parseAccelFile(fileName):
    with open(fileName, "r") as f:
        lines = f.readlines()
        lines = [line.split() for line in lines[5:]]

    tagID = int(fileName[-14:-9])
    
    obsArr = []
    for line in lines:
        obs = {}
        seconds, fracSeconds = divmod(float(line[5]),1)
        time = datetime(year=int(line[0]),month=int(line[1]), day=int(line[2]), hour=int(line[3]), minute=int(line[4]), second=int(seconds), microsecond=int(fracSeconds*1000000))
        obs["tagID"] = tagID
        obs["time"] = time
        obs["X"] = float(line[6])
        obs["Y"] = float(line[7])
        obs["Z"] = float(line[8])
        obs["mag"] = float(line[9])
        obsArr.append(obs)

    df = pd.DataFrame(obsArr)

    if USE_PICKLE:
        df.to_pickle(fileName[:-9]+"_Accel.pkl")
    else:
        df.to_csv(fileName[:-9]+"_Accel.csv",index=False)

wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.startswith("Obs") and f.endswith("Accel.txt")]

for fileName in wantedFiles:
    parseAccelFile(fileName)