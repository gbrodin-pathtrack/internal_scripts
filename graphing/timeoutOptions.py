import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from os import listdir
from os.path import isfile, join

#run processSatsFile on every file in root directory that ends with "_GPS.csv"
wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_GPS.csv")]

fileName = wantedFiles[0]

#read file into data frame
fullDF = pd.read_csv(fileName)
#convert datetime string to datetime
fullDF["fixTime"] = pd.to_datetime(fullDF["fixTime"])

#create new dataframe from rows with satelite ID of 0, these are dummy rows with only obs info attached
obsDF = pd.DataFrame(fullDF.loc[fullDF["ID"] == 0]).reset_index(drop=True)
#drop sat info columns
obsDF.drop([col for col in obsDF.columns if col in ["ID","CNR","codePhase","dopplerMS","dopplerHz"]],axis=1,inplace=True)

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

plt.show()