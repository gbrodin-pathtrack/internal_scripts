import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import datetime
from os import listdir
from os.path import isfile, join
import sys

#Set to true to display graphs
GRAPH = False

#Set to true to show specific num SV stats on GNSS
GNSS_GPS = False
GNSS_BEIDOU = False
GNSS_GALILEO = False

#ADC ref is 1V, 8bit scale = 255 divisions, voltage read is 1/5 of actual vbatt so * 5
VBATT_SCALE = (5/255)

def processSatsFile(fileName):
    #show which file is being processed
    print("*"*100)
    print(fileName)
    print()

    #read file into data frame
    fullDF = pd.read_csv(fileName)

    #get rows with satelite ID of 0, these are dummy rows with only obs info attached
    obsDF = fullDF.loc[fullDF["ID"] == 0]

    #only print cumulative stats for individual tag files
    if(fileName.startswith("Obs")):
        print("-"*50)
        print("Cummulative stats:")
        print("-"*50)
        print("Total on time: %.1fs" % (np.sum(obsDF["TTF"])/10))
        print()
        print("Battery Voltage Dropped: %.2fV" % ((np.mean(obsDF.head(10)["vbatt"]) - np.mean(obsDF.tail(10)["vbatt"]))*VBATT_SCALE))
        print()
        if("dopplerMS" in fullDF.columns):
            print("Max dopplerMS: %d",fullDF["dopplerMS"].max())
            print("Min dopplerMS: %d",fullDF["dopplerMS"].min())
            print()
        if("dopplerHz" in fullDF.columns):
            print("Max dopplerHz: %d",fullDF["dopplerHz"].max())
            print("Min dopplerHz: %d",fullDF["dopplerHz"].min())
            print()


    print("-"*50)
    print("Per observable stats:")
    print("-"*50)

    print("Time to fix:")
    print(" - Average: %.2fs" % (np.mean(obsDF["TTF"])/10))
    print(" - 90th Percentile: %.1fs" % (np.percentile(obsDF["TTF"], 90)/10))
    print(" - 10th Percentile: %.1fs" % (np.percentile(obsDF["TTF"], 10)/10))
    print(" - Standard Deviation: %.1fs" % (np.std(obsDF["TTF"])/10))
    print()

    print("Num SVs:")
    print(" - Average: %.2f" % np.mean(obsDF["numSV"]))
    print(" - 90th Percentile: %.1f" % np.percentile(obsDF["numSV"], 90))
    print(" - 10th Percentile: %.1f" % np.percentile(obsDF["numSV"], 10))
    print(" - Standard Deviation: %.1f" % np.std(obsDF["numSV"]))
    print()

    if(GNSS_GPS):
        print("GPS SVs:")
        print(" - Average: %.2f" % np.mean(obsDF["numGPS"]))
        print(" - 90th Percentile: %.1f" % np.percentile(obsDF["numGPS"], 90))
        print(" - 10th Percentile: %.1f" % np.percentile(obsDF["numGPS"], 10))
        print(" - Standard Deviation: %.1f" % np.std(obsDF["numGPS"]))
        print()

    if(GNSS_GALILEO):
        print("Galileo SVs:")
        print(" - Average: %.2f" % np.mean(obsDF["numGalileo"]))
        print(" - 90th Percentile: %.1f" % np.percentile(obsDF["numGalileo"], 90))
        print(" - 10th Percentile: %.1f" % np.percentile(obsDF["numGalileo"], 10))
        print(" - Standard Deviation: %.1f" % np.std(obsDF["numGalileo"]))
        print()

    if(GNSS_BEIDOU):
        print("Beidou SVs:")
        print(" - Average: %.2f" % np.mean(obsDF["numBeiDou"]))
        print(" - 90th Percentile: %.1f" % np.percentile(obsDF["numBeiDou"], 90))
        print(" - 10th Percentile: %.1f" % np.percentile(obsDF["numBeiDou"], 10))
        print(" - Standard Deviation: %.1f" % np.std(obsDF["numBeiDou"]))
        print()

    print("-"*50)
    print("Per satellite stats:")
    print("-"*50)

    gpsSats = fullDF.loc[(1 <= fullDF["ID"]) & (fullDF["ID"] <= 32)]
    beiSats = fullDF.loc[(101 <= fullDF["ID"]) & (fullDF["ID"] <= 163)]
    galSats = fullDF.loc[(201 <= fullDF["ID"]) & (fullDF["ID"] <= 236)]

    #print stats for each GNSS present
    if(len(gpsSats)):
        print("GPS CNR:")
        print(" - Average: %.2f" % np.mean(gpsSats["CNR"]))
        print(" - 90th Percentile: %.1f" % np.percentile(gpsSats["CNR"], 90))
        print(" - 10th Percentile: %.1f" % np.percentile(gpsSats["CNR"], 10))
        print(" - Standard Deviation: %.1f" % np.std(gpsSats["CNR"]))
        print()

    if(len(beiSats)):
        print("BeiDou CNR:")
        print(" - Average: %.2f" % np.mean(beiSats["CNR"]))
        print(" - 90th Percentile: %.1f" % np.percentile(beiSats["CNR"], 90))
        print(" - 10th Percentile: %.1f" % np.percentile(beiSats["CNR"], 10))
        print(" - Standard Deviation: %.1f" % np.std(beiSats["CNR"]))
        print()

    if(len(galSats)):
        print("Galileo CNR:")
        print(" - Average: %.2f" % np.mean(galSats["CNR"]))
        print(" - 90th Percentile: %.1f" % np.percentile(galSats["CNR"], 90))
        print(" - 10th Percentile: %.1f" % np.percentile(galSats["CNR"], 10))
        print(" - Standard Deviation: %.1f" % np.std(galSats["CNR"]))
        print()
    
    #Do graph stuff
    if GRAPH:
        #plot time to fix counts
        ttfCounts = obsDF["TTF"].value_counts(normalize=True).sort_index()
        plt.title("Time to fix relative frequency")
        plt.ylabel("Relative frequency")
        plt.xlabel("Time to fix (s)")
        plt.plot(ttfCounts.index/10, ttfCounts.values, label=fileName)


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
        self.file.flush()

#duplicate print messages into an output file
sys.stdout = Logger()

#run processSatsFile on every file in root directory that ends with "_sats.csv"
onlyfiles = [f for f in listdir("./") if isfile(join("./", f))]
for file in onlyfiles:
    if file.endswith("_sats.csv"):
        processSatsFile(file)

if GRAPH:
    plt.legend(loc="best")
    plt.show()