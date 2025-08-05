from os import listdir
from os.path import isfile, join
import pandas as pd
import numpy as np

USE_PICKLE = True

def calcAngle(reading):
    if reading.mag < 0.9 or reading.mag > 1.1:
        return np.NaN
    return np.degrees(np.arcsin(abs(reading.X)/reading.mag))

def parseAccelFile(fileName):
    df = pd.read_csv(fileName,sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)

    df["datetime"] = pd.to_datetime(df[["year","month","day","hour","minute","second"]])

    df["angle"] = df.apply(lambda x: calcAngle(x), axis=1)

    df["tagID"] = int(fileName[-18:-13])

    if USE_PICKLE:
        df.to_pickle(fileName[:-13]+"_ImmersionAccel.pkl")
    else:
        df.to_csv(fileName[:-13]+"_ImmersionAccel.csv",index=False)

wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.startswith("Obs") and f.endswith("AccWetDry.txt")]

for fileName in wantedFiles:
    parseAccelFile(fileName)