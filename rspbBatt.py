import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join
import os
from datetime import datetime

ROOT = "./z_RSPB/battery/data/"

metaDF = pd.read_csv(ROOT+"meta.csv",sep=",")

metaDF["deploymentDatetime"] = pd.to_datetime(metaDF[["year","month","day","hour","minute"]])
metaDF["deploymentDatetime"] = metaDF["deploymentDatetime"].dt.tz_localize("Europe/London").dt.tz_convert("UTC")

obsDFs = {}

wantedFiles = [f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.startswith("Obs") and f.endswith("GPS_Obs.pkl")]

for file in wantedFiles:
    fileTagIDIndex = file.find("Tag")
    fileTagID = int(file[fileTagIDIndex+3:fileTagIDIndex+8])
    obsDFs[fileTagID] = pd.read_pickle(ROOT+file).sort_values("datetime")
    #obsDFs[fileTagID] = obsDFs[fileTagID][obsDFs[fileTagID]["datetime"] >= datetime(2025,6,29)]

def removeUnwantedFiles():
    global ROOT
    global metaDF

    outputFiles = [f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.startswith("Obs") and f.endswith(".pkl")]

    for file in outputFiles:
        fileTagIDIndex = file.find("Tag")
        fileTagID = int(file[fileTagIDIndex+3:fileTagIDIndex+8])
        if fileTagID not in metaDF.tagID.values:
            os.remove(ROOT+file)

        
def verifyFiles():
    global ROOT
    global metaDF
    global obsDFs

    lessThanMeta = []
    moreThanMeta = []
    equalToMeta = []
    diffs = []

    tags = []

    metaCounts = []
    obsCounts = []

    for tagID, obsDF in obsDFs.items():
        metaRows = metaDF.loc[metaDF.tagID == tagID]
        if len(metaRows) != 1:
            print("Not 1 meta row for tag ID",tagID)
            continue
        metaCount = metaRows.numPoints.values[0]
        metaDeployment = metaRows.deploymentDatetime.values[0]
        obsCount = len(obsDF)
        filteredDF = obsDF[obsDF["datetime"] >= metaDeployment]#.drop_duplicates(subset=["datetime"])
        filteredObsCount = len(filteredDF)
        diffs.append(obsCount-metaCount)
        if obsCount < metaCount:
            lessThanMeta.append(tagID)
        elif obsCount > metaCount:
            moreThanMeta.append(tagID)
        else:
            equalToMeta.append(tagID)
        tags.append({"tagID":tagID,"RSPB count":metaCount,"Pathtrack Count (unfiltered)":obsCount, "Pathtrack Count (filtered)":filteredObsCount,"Diff (unfiltered)":obsCount-metaCount,"Diff (filtered)":filteredObsCount-metaCount})
        metaCounts.append(metaCount)
        obsCounts.append(obsCount)

    # print("Less than RSPBs number:")
    # print(", ".join([str(id) for id in lessThanMeta]))
    # print("More than RSPBs number:")
    # print(", ".join([str(id) for id in moreThanMeta]))
    # print("Equal to RSPBs number:")
    # print(", ".join([str(id) for id in equalToMeta]))
    
    countDF = pd.DataFrame(tags).sort_values("Diff (unfiltered)")
    countDF.to_csv(ROOT+"obsCount.csv",header=True,index=False)

def addBsMeta():
    global ROOT
    global metaDF

    bsMetaDF = pd.read_csv(ROOT+"BS_meta.csv",sep=",")

    def getInfo(tagID) -> tuple[int, int, float]:
        tagLines = bsMetaDF[bsMetaDF.tagID == tagID]
        numLines = len(tagLines)
        numTransmissions = len(tagLines[tagLines.transmissionStart == True])
        fastFraction = len(tagLines[tagLines.fastMode == True])/numLines
        return numLines, numTransmissions, fastFraction

    metaDF["numLines"], metaDF["numTransmissions"], metaDF["fastFraction"] = zip(*metaDF.apply(lambda x: getInfo(x.tagID), axis=1))
    metaDF.to_csv(ROOT+"meta.csv",header=True,index=False)

def batteryUsage():
    global ROOT
    global metaDF
    global obsDFs

    tags = []

    for tagID, obsDF in obsDFs.items():
        metaRows = metaDF.loc[metaDF.tagID == tagID]
        if len(metaRows) != 1:
            print("Not 1 meta row for tag ID",tagID)
            continue

        metaTimeout = metaRows.reducedTimeout.values[0]
        metaLines = metaRows.numLines.values[0]
        metaStarts = metaRows.numTransmissions.values[0]
        metaFast = metaRows.fastFraction.values[0]
        onTime = sum(obsDF.TTF.values)
        numPoints = len(obsDF)
        startV = obsDF.iloc[0].vbatt
        endV = obsDF.iloc[numPoints-1].vbatt
        dropV = startV - endV
        dropPerTime = dropV/onTime        

        tags.append({"tagID":tagID,"reducedTimeout":metaTimeout,"onTime":onTime,"numPoints":numPoints,
                     "startV":startV,"endV":endV,"dropV":dropV,"dropPerTime":dropPerTime,
                     "numLines":metaLines, "numTransmissions":metaStarts,"fastFraction":metaFast})

    battDF = pd.DataFrame(tags)
    battDF.to_csv(ROOT+"batt.csv",header=True,index=False)

def countEarly():
    global ROOT
    global obsDFs

    tags = []

    for tagID, obsDF in obsDFs.items():
        total = len(obsDF)
        before = len(obsDF[obsDF["datetime"] < datetime(2025,6,29)])
        after = len(obsDF[obsDF["datetime"] >= datetime(2025,6,29)])
        tags.append({"tagID":tagID,"total":total,"before":before,"after":after})

    countDF = pd.DataFrame(tags)
    countDF.to_csv(ROOT+"testCount.csv",header=True,index=False)

#batteryUsage()
#removeUnwantedFiles()
verifyFiles()
#addBsMeta()
#countEarly()