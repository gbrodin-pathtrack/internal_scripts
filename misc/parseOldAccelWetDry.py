from os import listdir
from os.path import isfile, join
import pandas as pd
from datetime import datetime, timedelta

USE_PICKLE = True

def convertDatetime(x):
    dt = datetime(year=int(x.year), month=1, day=1)
    offset = timedelta(days=(int(x.day) - 1),seconds=int(x.second))
    dt += offset
    return pd.to_datetime(dt)

def parseAccelFile(fileName):
    df = pd.read_csv(fileName,sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)

    df["datetime"] = pd.to_datetime(df[["year","month","day","hour","minute","second"]])

    df["tagID"] = int(fileName[-18:-13])

    if USE_PICKLE:
        df.to_pickle(fileName[:-13]+"_ImmersionAccel.pkl")
    else:
        df.to_csv(fileName[:-13]+"_ImmersionAccel.csv",index=False)

wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.startswith("Obs") and f.endswith("AccWetDry.txt")]

for fileName in wantedFiles:
    parseAccelFile(fileName)