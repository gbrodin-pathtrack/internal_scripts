import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join
import sys

USE_PICKLE = False

ROOT = "./"

def processSatsFile(fileName):
    #show which file is being processed
    print("*"*100)
    print(fileName)
    print()

    #read file into data frame
    if USE_PICKLE:
        satsDF = pd.read_pickle(fileName)
    else:
        satsDF = pd.read_csv(fileName)

    #get rows with relevant sat IDs for each GNSS
    gpsSats = satsDF.loc[(1 <= satsDF["ID"]) & (satsDF["ID"] <= 32)]
    beiSats = satsDF.loc[(101 <= satsDF["ID"]) & (satsDF["ID"] <= 163)]
    galSats = satsDF.loc[(201 <= satsDF["ID"]) & (satsDF["ID"] <= 236)]

    #print stats for each GNSS present
    if(len(gpsSats)):
        print("GPS CNR:")
        print(" - Average: %.2f" % np.mean(gpsSats["CNR"]))
        print(" - Maximum: %d" % gpsSats["CNR"].max())
        print(" - 90th Percentile: %d" % np.percentile(gpsSats["CNR"], 90))
        print(" - 10th Percentile: %d" % np.percentile(gpsSats["CNR"], 10))
        print(" - Minimum: %d" % gpsSats["CNR"].min())
        print(" - Standard Deviation: %.1f" % np.std(gpsSats["CNR"]))
        print()

    if(len(beiSats)):
        print("BeiDou CNR:")
        print(" - Average: %.2f" % np.mean(beiSats["CNR"]))
        print(" - Maximum: %d" % beiSats["CNR"].max())
        print(" - 90th Percentile: %d" % np.percentile(beiSats["CNR"], 90))
        print(" - 10th Percentile: %d" % np.percentile(beiSats["CNR"], 10))
        print(" - Minimum: %d" % beiSats["CNR"].min())
        print(" - Standard Deviation: %.1f" % np.std(beiSats["CNR"]))
        print()

    if(len(galSats)):
        print("Galileo CNR:")
        print(" - Average: %.2f" % np.mean(galSats["CNR"]))
        print(" - Maximum: %d" % galSats["CNR"].max())
        print(" - 90th Percentile: %d" % np.percentile(galSats["CNR"], 90))
        print(" - 10th Percentile: %d" % np.percentile(galSats["CNR"], 10))
        print(" - Minimum: %d" % galSats["CNR"].min())
        print(" - Standard Deviation: %.1f" % np.std(galSats["CNR"]))
        print()
        


#class to output printed values to terminal and output file
class Logger(object):
    def __init__(self):
        self.terminal = sys.stdout
        self.file = open(ROOT+"sat_summary.txt", "w")
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
wantedFiles = [ROOT + f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.endswith("_GPS_SVs"+wantedExtension) and "unique" in f]

#duplicate print messages into an output file, only if there are files to process
if len(wantedFiles) > 0:
    sys.stdout = Logger()

for file in wantedFiles:
    processSatsFile(file)
