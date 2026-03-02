import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join

USE_PICKLE = True

def checkSpacing(fileName):
    #load DF
    if USE_PICKLE:
        df = pd.read_pickle(fileName)
    else:
        df = pd.read_csv(fileName)
        df["datetime"] = pd.to_datetime(df["datetime"])

    #calc time diff
    df["timeDiff"] = df["datetime"].diff(1).dt.total_seconds()

    #drop first row as it has no time diff
    df = df.iloc[1:]

    #remove large time diffs caused by UHF offload/GPS burst mode
    df["gap"] = df["timeDiff"] > np.percentile(df["timeDiff"], 99)
    timeDiffs = df.loc[df["gap"] == False]["timeDiff"]

    #calc averages
    avgDiff = timeDiffs.mean()
    avgRate = 1/avgDiff

    #print summary
    print(fileName)
    print("Time difference:")
    print(" - Average: %.2fms (%.2fHz)" % ((avgDiff * 1000), avgRate))
    print(" - Std dev: %.2fms" % (timeDiffs.std() * 1000))
    print(" - Min: %.2fms" % (timeDiffs.min() * 1000))
    print(" - Max: %.2fms" % (timeDiffs.max() * 1000))
    print()


if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"
#get every file in root directory that ends with "_Accel" or "_VeDBA"
wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and (f.endswith("_Accel"+wantedExtension) or f.endswith("_VeDBA"+wantedExtension))]

for fileName in wantedFiles:
    checkSpacing(fileName)