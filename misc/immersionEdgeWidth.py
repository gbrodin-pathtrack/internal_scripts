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

immWantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_Immersion"+wantedExtension)]

immFileName = immWantedFiles[0]

#read files into data frames
if USE_PICKLE:
    immDF = pd.read_pickle(immFileName)
else:
    immDF = pd.read_csv(immFileName)

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

for tagImmDF in tagImmDFs.values():
    tagImmDF.drop(tagImmDF.loc[(tagImmDF.index % SUBSAMPLE) != 0].index, inplace=True)
    tagImmDF.reset_index(drop=True, inplace=True)
    prevWet = 0
    tagImmDF["prevWet"] = tagImmDF.apply(genPrevWet, axis=1)
    numEdges += len(tagImmDF.loc[(tagImmDF["immersed"] == False) & (tagImmDF["prevWet"] > 0)])
    numSingleEdges += len(tagImmDF.loc[(tagImmDF["immersed"] == False) & (tagImmDF["prevWet"] == 1)])

print("Percentage of single edges: %d%%" % ((numSingleEdges / numEdges) * 100))