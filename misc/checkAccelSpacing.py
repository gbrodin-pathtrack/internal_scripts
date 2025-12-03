import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join

USE_PICKLE = True

def checkSpacing(fileName):
    if USE_PICKLE:
        df = pd.read_pickle(fileName)
    else:
        df = pd.read_csv(fileName)
        df["datetime"] = pd.to_datetime(df["datetime"])

    df["timeDiff"] = df["datetime"].diff(1).dt.total_seconds()

    avgDiff = df["timeDiff"].mean()
    avgRate = 1/avgDiff

    print(fileName)
    print("Time difference:")
    print(" - Average: %.2fms (%.2fHz)" % ((avgDiff * 1000), avgRate))
    print(" - Std dev: %.2fms" % (df["timeDiff"].std() * 1000))
    print(" - Min: %.2fms" % (df["timeDiff"].min() * 1000))
    print(" - Max: %.2fms" % (df["timeDiff"].max() * 1000))
    print()


if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"
#get every file in root directory that ends with "_GPS"
wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_Accel"+wantedExtension)]

for fileName in wantedFiles:
    checkSpacing(fileName)