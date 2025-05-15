import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join
import sys

USE_PICKLE = False

def processObsFile(fileName):
    #show which file is being processed
    print("*"*100)
    print(fileName)
    print()

    #read file into data frame
    if USE_PICKLE:
        obsDF = pd.read_pickle(fileName)
    else:
        obsDF = pd.read_csv(fileName)
    #convert datetime string to datetime
    obsDF["time"] = pd.to_datetime(obsDF["time"])
    obsDF["startTime"] = pd.to_datetime(obsDF["startTime"])

    print("-"*50)
    print("Cumulative stats:")
    print("-"*50)

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
    print(" - Maximum: %.1f" % obsDF["numSV"].max())
    print(" - 90th Percentile: %.1f" % np.percentile(obsDF["numSV"], 90))
    print(" - 10th Percentile: %.1f" % np.percentile(obsDF["numSV"], 10))
    print(" - Standard Deviation: %.1f" % np.std(obsDF["numSV"]))
    print()

    # if(obsDF["numGPS"].max()>0 and (obsDF["numGalileo"].max()>0 or obsDF["numBeiDou"].max()>0)):
    #     print("GPS SVs:")
    #     print(" - Average: %.2f" % np.mean(obsDF["numGPS"]))
    #     print(" - 90th Percentile: %.1f" % np.percentile(obsDF["numGPS"], 90))
    #     print(" - 10th Percentile: %.1f" % np.percentile(obsDF["numGPS"], 10))
    #     print(" - Standard Deviation: %.1f" % np.std(obsDF["numGPS"]))
    #     print()

    # if(obsDF["numGalileo"].max()>0):
    #     print("Galileo SVs:")
    #     print(" - Average: %.2f" % np.mean(obsDF["numGalileo"]))
    #     print(" - 90th Percentile: %.1f" % np.percentile(obsDF["numGalileo"], 90))
    #     print(" - 10th Percentile: %.1f" % np.percentile(obsDF["numGalileo"], 10))
    #     print(" - Standard Deviation: %.1f" % np.std(obsDF["numGalileo"]))
    #     print()

    # if(obsDF["numBeiDou"].max()>0):
    #     print("Beidou SVs:")
    #     print(" - Average: %.2f" % np.mean(obsDF["numBeiDou"]))
    #     print(" - 90th Percentile: %.1f" % np.percentile(obsDF["numBeiDou"], 90))
    #     print(" - 10th Percentile: %.1f" % np.percentile(obsDF["numBeiDou"], 10))
    #     print(" - Standard Deviation: %.1f" % np.std(obsDF["numBeiDou"]))
    #     print()

    #only print timing stats for individual tag files
    if(fileName.startswith("Obs")):
        print("-"*50)
        print("Timing stats:")
        print("-"*50)

        #obsDF["startTime"] = obsDF["time"] - pd.to_timedelta(obsDF["TTF"],unit="s")
        obsDF["startTimeDiff"] = obsDF["startTime"].diff(1).dt.total_seconds()
        obsDF["startTimeDiffDiff"] = obsDF["startTimeDiff"].diff(1)

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
        self.file = open("obs_summary.txt", "w")
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
wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_GPS_Obs"+wantedExtension)]

#duplicate print messages into an output file, only if there are files to process
if len(wantedFiles) > 0:
    sys.stdout = Logger()

for file in wantedFiles:
    processObsFile(file)
