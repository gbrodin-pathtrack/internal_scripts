import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join
import sys

USE_PICKLE = False

def processSatsFile(fileName):
    #show which file is being processed
    print("*"*100)
    print(fileName)
    print()

    #read file into data frame
    if USE_PICKLE:
        fullDF = pd.read_pickle(fileName)
    else:
        fullDF = pd.read_csv(fileName)
    #convert datetime string to datetime
    fullDF["fixTime"] = pd.to_datetime(fullDF["fixTime"])

    #create new dataframe from rows with satelite ID of 0, these are dummy rows with only obs info attached
    obsDF = pd.DataFrame(fullDF.loc[fullDF["ID"] == 0]).reset_index(drop=True)
    #drop sat info columns
    obsDF.drop([col for col in obsDF.columns if col in ["ID","CNR","codePhase","dopplerMS","dopplerHz"]],axis=1,inplace=True)

    #drop dummy rows from data frame
    fullDF.drop(fullDF.loc[fullDF["ID"] == 0].index, inplace=True)
    fullDF.reset_index(inplace=True, drop=True)

    print("-"*50)
    print("Cumulative stats:")
    print("-"*50)
    # if("dopplerMS" in fullDF.columns):
    #     print("Max dopplerMS:",fullDF["dopplerMS"].max())
    #     print("Min dopplerMS:",fullDF["dopplerMS"].min())
    #     print()
    # if("dopplerHz" in fullDF.columns):
    #     print("Max dopplerHz:",fullDF["dopplerHz"].max())
    #     print("Min dopplerHz:",fullDF["dopplerHz"].min())
    #     print()

    #only print battery stats for individual tag files
    if(fileName.startswith("Obs")):
        print("Battery Voltage Dropped: %.2fV" % ((np.mean(obsDF.head(10)["vbatt"]) - np.mean(obsDF.tail(10)["vbatt"]))))
        print()

    totalTime = np.sum(obsDF["TTF"])
    totalAttempts = len(obsDF["numSV"])
    totalSuccesses = len(obsDF.loc[obsDF["numSV"] > 4])
    print("Total:")
    print(" - GPS on time: %.1fs" % totalTime)
    print(" - GPS attempts: %d" % totalAttempts)
    print(" - GPS successes: %d" % totalSuccesses)
    print()
    print("Success Rate: %.2f%%" % ((totalSuccesses/totalAttempts)*100))
    print()
    print("On time per fix: %.2fs" % (totalTime/totalSuccesses))
    print()

    totalFailGPSConfig = len(obsDF[obsDF["TTF"] == 250])
    if totalFailGPSConfig:
        print("WARNING: %d GPS attempts failed to config GPS" %totalFailGPSConfig)


    print("-"*50)
    print("Per observable stats:")
    print("-"*50)

    print("Time to fix:")
    print(" - Average: %.2fs" % (np.mean(obsDF["TTF"])))
    print(" - 90th Percentile: %.1fs" % (np.percentile(obsDF["TTF"], 90)))
    print(" - 10th Percentile: %.1fs" % (np.percentile(obsDF["TTF"], 10)))
    print(" - Standard Deviation: %.1fs" % (np.std(obsDF["TTF"])))
    print()

    print("Num SVs:")
    print(" - Average: %.2f" % np.mean(obsDF["numSV"]))
    print(" - 90th Percentile: %.1f" % np.percentile(obsDF["numSV"], 90))
    print(" - 10th Percentile: %.1f" % np.percentile(obsDF["numSV"], 10))
    print(" - Standard Deviation: %.1f" % np.std(obsDF["numSV"]))
    print()

    if(obsDF["numGPS"].max()>0 and (obsDF["numGalileo"].max()>0 or obsDF["numBeiDou"].max()>0)):
        print("GPS SVs:")
        print(" - Average: %.2f" % np.mean(obsDF["numGPS"]))
        print(" - 90th Percentile: %.1f" % np.percentile(obsDF["numGPS"], 90))
        print(" - 10th Percentile: %.1f" % np.percentile(obsDF["numGPS"], 10))
        print(" - Standard Deviation: %.1f" % np.std(obsDF["numGPS"]))
        print()

    if(obsDF["numGalileo"].max()>0):
        print("Galileo SVs:")
        print(" - Average: %.2f" % np.mean(obsDF["numGalileo"]))
        print(" - 90th Percentile: %.1f" % np.percentile(obsDF["numGalileo"], 90))
        print(" - 10th Percentile: %.1f" % np.percentile(obsDF["numGalileo"], 10))
        print(" - Standard Deviation: %.1f" % np.std(obsDF["numGalileo"]))
        print()

    if(obsDF["numBeiDou"].max()>0):
        print("Beidou SVs:")
        print(" - Average: %.2f" % np.mean(obsDF["numBeiDou"]))
        print(" - 90th Percentile: %.1f" % np.percentile(obsDF["numBeiDou"], 90))
        print(" - 10th Percentile: %.1f" % np.percentile(obsDF["numBeiDou"], 10))
        print(" - Standard Deviation: %.1f" % np.std(obsDF["numBeiDou"]))
        print()

    print("-"*50)
    print("Per satellite stats:")
    print("-"*50)

    #get rows with relevant sat IDs for each GNSS
    gpsSats = fullDF.loc[(1 <= fullDF["ID"]) & (fullDF["ID"] <= 32)]
    beiSats = fullDF.loc[(101 <= fullDF["ID"]) & (fullDF["ID"] <= 163)]
    galSats = fullDF.loc[(201 <= fullDF["ID"]) & (fullDF["ID"] <= 236)]

    #print stats for each GNSS present
    if(len(gpsSats)):
        print("GPS CNR:")
        print(" - Average: %.2f" % np.mean(gpsSats["CNR"]))
        print(" - Maximum: %.1f" % gpsSats["CNR"].max())
        print(" - 90th Percentile: %.1f" % np.percentile(gpsSats["CNR"], 90))
        print(" - 10th Percentile: %.1f" % np.percentile(gpsSats["CNR"], 10))
        print(" - Minimum: %.1f" % gpsSats["CNR"].min())
        print(" - Standard Deviation: %.1f" % np.std(gpsSats["CNR"]))
        print()

    if(len(beiSats)):
        print("BeiDou CNR:")
        print(" - Average: %.2f" % np.mean(beiSats["CNR"]))
        print(" - Maximum: %.1f" % beiSats["CNR"].max())
        print(" - 90th Percentile: %.1f" % np.percentile(beiSats["CNR"], 90))
        print(" - 10th Percentile: %.1f" % np.percentile(beiSats["CNR"], 10))
        print(" - Minimum: %.1f" % beiSats["CNR"].min())
        print(" - Standard Deviation: %.1f" % np.std(beiSats["CNR"]))
        print()

    if(len(galSats)):
        print("Galileo CNR:")
        print(" - Average: %.2f" % np.mean(galSats["CNR"]))
        print(" - Maximum: %.1f" % galSats["CNR"].max())
        print(" - 90th Percentile: %.1f" % np.percentile(galSats["CNR"], 90))
        print(" - 10th Percentile: %.1f" % np.percentile(galSats["CNR"], 10))
        print(" - Minimum: %.1f" % galSats["CNR"].min())
        print(" - Standard Deviation: %.1f" % np.std(galSats["CNR"]))
        print()

    #only print timing stats for individual tag files
    if(fileName.startswith("Obs")):
        print("-"*50)
        print("Timing stats:")
        print("-"*50)

        obsDF["startTime"] = obsDF["fixTime"] - pd.to_timedelta(obsDF["TTF"],unit="s")
        obsDF["startTimeDiff"] = obsDF["startTime"].diff(1).dt.total_seconds()
        obsDF["startTimeDiffDiff"] = obsDF["startTimeDiff"].diff(1)
        obsDF["startTimeDiffDiff"] = obsDF["startTimeDiffDiff"]

        print("Time between GPS attempt starts:")
        print(" - Average: %.2fs" % (np.mean(obsDF["startTimeDiff"])))
        print(" - Maximum: %.2fs" % obsDF["startTimeDiff"].max())
        print(" - Minimum: %.2fs" % obsDF["startTimeDiff"].min())
        print()
        #Comment in to see obs with max and min time diff
        # print(obsDF.iloc[obsDF["startTimeDiff"].idxmax()-4 : obsDF["startTimeDiff"].idxmax()+3])
        # print()
        # print(obsDF.iloc[obsDF["startTimeDiff"].idxmin()-4 : obsDF["startTimeDiff"].idxmin()+3])
        # print()
        # print()
        # print(obsDF[obsDF["startTimeDiffDiff"].abs() > 5])
        # print()
        # print(obsDF.to_string())

        clockResets = obsDF.loc[obsDF["startTimeDiff"] < 0]
        if(len(clockResets)>0 and fileName.startswith("Obs")):
            print()
            print("WARNING: Negative time diff(s):")
            print()
            print(clockResets)
            print()
        


#class to output printed values to terminal and output file
class Logger(object):
    def __init__(self):
        self.terminal = sys.stdout
        self.file = open("sat_summary.txt", "w")
    def __del__(self):
        self.file.close()
    def write(self, message):
        self.terminal.write(message)
        self.file.write(message)  
    def flush(self):
        self.terminal.flush()
        self.file.flush()

if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"
#get every file in root directory that ends with "_GPS"
wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_GPS"+wantedExtension)]

#duplicate print messages into an output file, only if there are files to process
if len(wantedFiles) > 0:
    sys.stdout = Logger()

for file in wantedFiles:
    processSatsFile(file)
