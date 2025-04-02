import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from os import listdir
from os.path import isfile, join

USE_PICKLE = True
ZERO_SCALE = False

if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"
#get every file in root directory that ends with "_GPS"
wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_GPS_Obs"+wantedExtension)]

fileName = wantedFiles[0]

#read file into data frame
if USE_PICKLE:
    obsDF = pd.read_pickle(fileName)
else:
    obsDF = pd.read_csv(fileName)
#convert datetime string to datetime
obsDF["fixTime"] = pd.to_datetime(obsDF["fixTime"])

timeoutOptions = np.arange(2,9,1)
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
if ZERO_SCALE:
    ax1.set_ylim(0,None)

ax2 = ax1.twinx()

col = "tab:blue"
ax2.set_ylabel("Success Rate (%)", color=col)
ax2.plot(timeoutDF["timeout"],timeoutDF["successRate"], color=col)
ax2.tick_params(axis="y", labelcolor=col)
if ZERO_SCALE:
    ax2.set_ylim(0,100)

plt.show()