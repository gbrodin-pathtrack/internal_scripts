import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join

USE_PICKLE = True

if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"
gpsWantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_GPS_Obs"+wantedExtension)]
immWantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_Immersion"+wantedExtension)]

gpsFileName = gpsWantedFiles[0]
immFileName = immWantedFiles[0]

#read files into data frames
if USE_PICKLE:
    obsDF = pd.read_pickle(gpsFileName)
    immDF = pd.read_pickle(immFileName)
else:
    obsDF = pd.read_csv(gpsFileName)
    immDF = pd.read_csv(immFileName)

def getEdgeDistance(obs):
    global immDF
    tagImmDF = immDF.loc[immDF["tagID"] == obs.tagID]
    tagImmDF["timeDiff"] = (tagImmDF["datetime"] - obs.datetime).dt.total_seconds()
    triggerIdx = tagImmDF.loc[tagImmDF["timeDiff"] < 0, "timeDiff"].idxmax()
    if tagImmDF.iloc[triggerIdx].immersed == True:
        return -1
    distance = 0
    for _ in range(8):
        if tagImmDF.iloc[triggerIdx-distance-1].immersed == True:
            return distance
        distance += 1
    return -2

obsDF["edgeDistance"] = obsDF.apply(getEdgeDistance, axis=1)

for distance in range(8):
    distanceDF = obsDF.loc[obsDF["edgeDistance"] == distance]
    print("Num SVs for edge distance %d:" % distance)
    print(" - Success Rate (>=5): %d%%" % ((len(distanceDF.loc[distanceDF["numSV"] >= 5])/len(distanceDF))*100))
    print(" - Average: %.2f" % np.mean(distanceDF["numSV"]))
    print(" - Maximum: %.1f" % distanceDF["numSV"].max())
    print(" - 90th Percentile: %.1f" % np.percentile(distanceDF["numSV"], 90))
    print(" - 10th Percentile: %.1f" % np.percentile(distanceDF["numSV"], 10))
    print(" - Standard Deviation: %.1f" % np.std(distanceDF["numSV"]))
    print()