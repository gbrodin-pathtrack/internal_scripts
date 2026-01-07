import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join

USE_PICKLE = True

SUBSAMPLE = 8

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

obsDF["cancelledZero"] = (obsDF["numSV"] == 0) & (obsDF["TTF"] >= 5)
obsDF["cancelledWet"] = ((obsDF["numSV"] == 0) & (obsDF["TTF"] < 5)) | ((obsDF["numSV"] > 0) & (obsDF["numSV"] < 5) & (obsDF["TTF"] < 20)) | ((obsDF["numSV"] == 5) & (obsDF["TTF"] < 5))

obsDF["cancelled"] = obsDF["cancelledZero"] | obsDF["cancelledWet"]
obsDF["saved"] = 20 - obsDF["TTF"]

tagImmDFs : dict[int, pd.DataFrame] = {}

for tagID in immDF["tagID"].unique():
    tagImmDFs[tagID] = immDF.loc[immDF["tagID"] == tagID].copy()

prevWet = 0

def genPrevWet(row):
    global prevWet
    ret = prevWet
    if row.immersed == True:
        prevWet += 1
    else:
        prevWet = 0
    return ret

numEdges = 0
numSingleEdges = 0

tagEdgeDFs : dict[int, pd.DataFrame] = {}

for tagImmDF in tagImmDFs.values():
    tagImmDF.drop(tagImmDF.loc[(tagImmDF.index % SUBSAMPLE) != 0].index, inplace=True)
    tagImmDF.reset_index(drop=True, inplace=True)
    prevWet = 0
    tagImmDF["prevWet"] = tagImmDF.apply(genPrevWet, axis=1)
    edgeDF = tagImmDF.loc[(tagImmDF["immersed"] == False) & (tagImmDF["prevWet"] > 0)].copy()
    numEdges += len(edgeDF)
    numSingleEdges += len(edgeDF.loc[edgeDF["prevWet"] == 1])
    tagEdgeDFs[edgeDF.tagID.iloc[0]] = edgeDF.reset_index(drop=True)

print("Percentage of single edges: %.1f%%" % ((numSingleEdges / numEdges) * 100))

print()

def getPrevWet(obs):
    global tagEdgeDFs
    tagEdgeDF = tagEdgeDFs[obs.tagID]
    tagEdgeDF["timeDiff"] = (tagEdgeDF["datetime"] - obs.datetime).dt.total_seconds()
    return tagEdgeDF.prevWet.iloc[tagEdgeDF.loc[tagEdgeDF["timeDiff"] < 0, "timeDiff"].idxmax()]

obsDF["prevWet"] = obsDF.apply(getPrevWet, axis=1)

singleDF = obsDF.loc[obsDF["prevWet"] == 1].copy()
multiDF = obsDF.loc[obsDF["prevWet"] > 1].copy()

print("Percent triggered by single wet: %.1f%%" % ((len(singleDF) / len(obsDF)) * 100))
print()

print("Triggered by single wet:")
print("Percent cancelled zero: %.1f%%" % ((len(singleDF.loc[singleDF["cancelledZero"] == True]) / len(singleDF)) * 100))
print("Percent cancelled wet: %.1f%%" % ((len(singleDF.loc[singleDF["cancelledWet"] == True]) / len(singleDF)) * 100))
print("Average cancel saving: %.2fs" % singleDF.loc[singleDF["cancelled"] == True, "saved"].mean())
print("Success rate of non cancelled: %.1f%%" % ((len(singleDF.loc[(singleDF["numSV"] >= 5) & (singleDF["cancelled"] == False)]) / len(singleDF.loc[singleDF["cancelled"] == False])) * 100))
print("Overall success rate: %.1f%%" % ((len(singleDF.loc[singleDF["numSV"] >= 5]) / len(singleDF)) * 100))

print()
print("Triggered by multiple wet:")
print("Percent cancelled zero: %.1f%%" % ((len(multiDF.loc[multiDF["cancelledZero"] == True]) / len(multiDF)) * 100))
print("Percent cancelled wet: %.1f%%" % ((len(multiDF.loc[multiDF["cancelledWet"] == True]) / len(multiDF)) * 100))
print("Average cancel saving: %.2fs" % multiDF.loc[multiDF["cancelled"] == True, "saved"].mean())
print("Success rate of non cancelled: %.1f%%" % ((len(multiDF.loc[(multiDF["numSV"] >= 5) & (multiDF["cancelled"] == False)]) / len(multiDF.loc[multiDF["cancelled"] == False])) * 100))
print("Overall success rate: %.1f%%" % ((len(multiDF.loc[multiDF["numSV"] >= 5]) / len(multiDF)) * 100))

print()
print("Success average on time: %.2f" % obsDF.loc[obsDF["numSV"] >= 5, "TTF"].mean())
print("Fail average on time: %.2f" % obsDF.loc[obsDF["numSV"] < 5, "TTF"].mean())