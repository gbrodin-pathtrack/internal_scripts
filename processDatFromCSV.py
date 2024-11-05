import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from os import listdir
from os.path import isfile, join
import sys

#Set to true to display graphs, output file won't be generated
GRAPH = False

#some graphs only support a single file being graphed, they will set this and exit early
singleGraph = False

#ADC ref is 1V, 8bit scale = 255 divisions, voltage read is 1/5 of actual vbatt so * 5
VBATT_SCALE = (5/255)

def processSatsFile(fileName):
    global singleGraph
    #show which file is being processed
    print("*"*100)
    print(fileName)
    print()

    #read file into data frame
    fullDF = pd.read_csv(fileName)
    #convert datetime string to datetime
    fullDF["datetime"] = pd.to_datetime(fullDF["datetime"])

    #create new dataframe from rows with satelite ID of 0, these are dummy rows with only obs info attached
    obsDF = pd.DataFrame(fullDF.loc[fullDF["ID"] == 0]).set_index(["obsNum"])
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
        print("Battery Voltage Dropped: %.2fV" % ((np.mean(obsDF.head(10)["vbatt"]) - np.mean(obsDF.tail(10)["vbatt"]))*VBATT_SCALE))
        print()

    totalTime = np.sum(obsDF["TTF"])
    totalAttempts = len(obsDF["numSV"])
    totalSuccesses = len(obsDF.loc[obsDF["numSV"] > 4])
    print("Total:")
    print(" - GPS on time: %.1fs" % totalTime)
    print(" - GPS attempts: %d" % totalAttempts)
    print(" - GPS successes: %d" % totalSuccesses)
    print()
    print("Success Rate: %.1f%%" % ((totalSuccesses/totalAttempts)*100))
    print()
    print("On time per fix: %.2fs" % (totalTime/totalSuccesses))
    print()


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

    if(obsDF["numGPS"].max()>0):
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

    print("-"*50)
    print("Timing stats:")
    print("-"*50)

    obsDF["timediff"] = obsDF["datetime"].diff(1)

    print("Time between fixes:")
    print(" - Average: %.2fs" % (np.mean(obsDF["timediff"])).total_seconds())
    print(" - Maximum: %.2fs" % obsDF["timediff"].max().total_seconds())
    print(" - Minimum: %.2fs" % obsDF["timediff"].min().total_seconds())
    print()

    #only warn about clock reset in tag specific file
    clockResets = obsDF.loc[obsDF["timediff"].dt.total_seconds() < 0]
    if(len(clockResets)>0 and fileName.startswith("Obs")):
        print()
        print("WARNING: Negative time diff(s):")
        print()
        print(clockResets)
        print()
    
    
    #Do graph stuff
    if GRAPH:
        #plot time to fix counts
        # ttfCounts = obsDF["TTF"].value_counts(normalize=True).sort_index()
        # plt.title("Time to fix relative frequency")
        # plt.ylabel("Relative frequency")
        # plt.xlabel("Time to fix (s)")
        # plt.plot(ttfCounts.index, ttfCounts.values, label=fileName)
        # plt.legend(loc="best")

        #plot success rate and on time per fix for different timeout options
        timeoutOptions = np.arange(0.1,20.1,0.1)
        timeoutDF = pd.DataFrame(timeoutOptions,columns=["timeout"])
        timeoutDF["onTime"] = timeoutDF.apply(lambda x: sum(obsDF.loc[obsDF["TTF"] < x.timeout]["TTF"]) + x.timeout*len(obsDF.loc[obsDF["TTF"] >= x.timeout]), axis=1)
        timeoutDF["successes"] = timeoutDF.apply(lambda x: len(obsDF.loc[(obsDF["TTF"] <= x.timeout) & (obsDF["numSV"] > 4)]), axis=1)
        timeoutDF["successRate"] = (timeoutDF["successes"]/len(obsDF["TTF"]))*100
        timeoutDF["onTimePerFix"] = timeoutDF["onTime"]/timeoutDF["successes"]

        singleGraph = True

        fig, ax1 = plt.subplots()

        plt.title("Timeout Options vs Performance")

        col = "tab:red"
        ax1.set_xlabel("Timeout (s)")
        ax1.set_ylabel("On time per fix (s)", color=col)
        ax1.plot(timeoutDF["timeout"], timeoutDF["onTimePerFix"], color=col)
        ax1.tick_params(axis="y", labelcolor=col)

        ax2 = ax1.twinx()

        col = "tab:blue"
        ax2.set_ylabel("Success Rate (%)", color=col)
        ax2.plot(timeoutDF["timeout"],timeoutDF["successRate"], color=col)
        ax2.tick_params(axis="y", labelcolor=col)


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
onlyfiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_sats.csv")]
for file in onlyfiles:
    processSatsFile(file)
    if singleGraph:
        break

if GRAPH:
    plt.show()