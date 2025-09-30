from os import listdir
from os.path import isfile, join
import pandas as pd
import numpy as np

USE_PICKLE = True

ROOT = "./"

CHUNK = 25
TAKE = 2

if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"

def resample(filename):
    #read file into data frame
    if USE_PICKLE:
        df = pd.read_pickle(filename)
    else:
        df = pd.read_csv(filename)
    #convert datetime string to datetime
    df["datetime"] = pd.to_datetime(df["datetime"])

    df["chunkIndex"] = df.index % CHUNK

    wantedChunkIndexes = np.linspace(0,int(CHUNK/TAKE),TAKE,dtype=int)

    subsampledDF = df[df["chunkIndex"].isin(wantedChunkIndexes)]

    df.drop(columns=["chunkIndex"],inplace=True)

    subsampleFilename = filename[:-4]+"_subsampled"+wantedExtension
    if USE_PICKLE:
        subsampledDF.to_pickle(subsampleFilename)
    else:
        subsampledDF.to_csv(subsampleFilename, header=True, index=False)

    df["vedbaChunk"] = df.index // 125

    vedbaChunks = df.groupby("vedbaChunk")

    def calcVedba(chunk):
        staticX = chunk.X.mean()
        staticY = chunk.Y.mean()
        staticZ = chunk.Z.mean()

        chunk["dynX"] = chunk.X - staticX
        chunk["dynY"] = chunk.Y - staticY
        chunk["dynZ"] = chunk.Z - staticZ

        chunk["dynMag"] = np.sqrt(chunk.dynX**2 + chunk.dynY**2 + chunk.dynZ**2)

        return np.mean(chunk.dynMag)

    vedbaDF = pd.DataFrame({
        #"tagID":vedbaChunks["tagID"].first(),
        "datetime":vedbaChunks["datetime"].first(),
        "avgVeDBA":vedbaChunks.apply(calcVedba)
    })

    vedbaFilename = filename[:-4]+"_vedba"+wantedExtension
    if USE_PICKLE:
        vedbaDF.to_pickle(vedbaFilename)
    else:
        vedbaDF.to_csv(vedbaFilename, header=True, index=False)

wantedFiles = [f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.endswith("_Accel"+wantedExtension)]

for file in wantedFiles:
    resample(ROOT+file)