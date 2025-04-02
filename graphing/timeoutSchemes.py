import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from os import listdir
from os.path import isfile, join

consecTimeoutsAT = 0
def currAdaptiveTimeout(obs, timeoutDefault, timeoutStep, timeoutMin):
    global consecTimeoutsAT

    currTimeout = max(timeoutMin, timeoutDefault-timeoutStep*consecTimeoutsAT)

    if obs.TTF >= currTimeout:
        consecTimeoutsAT += 1
    else:
        consecTimeoutsAT = 0
    return currTimeout


consecTimeoutsAI = 0
skipCountAI = 0
def currAdaptiveInterval(obs, timeoutDefault, skipStep, skipMax):
    global consecTimeoutsAI
    global skipCountAI

    numSkips = min(skipMax, consecTimeoutsAI-1)
    if numSkips > 0:
        skipCountAI += skipStep
        if skipCountAI > numSkips:
            skipCountAI = 0
        else:
            return 0

    if obs.TTF >= timeoutDefault:
        consecTimeoutsAI += 1
    else:
        consecTimeoutsAI = 0
    return timeoutDefault


consecTimeoutsATI = 0
skipCountATI = 0
def currAdaptiveTimeoutInterval(obs, timeoutDefault, timeoutStep, timeoutMin, skipStep, skipMax):
    global consecTimeoutsATI
    global skipCountATI

    currTimeout = max(timeoutMin, timeoutDefault-timeoutStep*consecTimeoutsATI)
    numSkips = min(skipMax, consecTimeoutsATI-1)
    if numSkips > 0:
        skipCountATI += skipStep
        if skipCountATI > numSkips:
            skipCountATI = 0
        else:
            return 0

    if obs.TTF >= currTimeout:
        consecTimeoutsATI += 1
    else:
        consecTimeoutsATI = 0
    return currTimeout
        

USE_PICKLE = True

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

schemeDFArr = []

#calc on time and num successes for flat timeout options
flatTimeouts = [8,6]
faltTimeDF = pd.DataFrame(flatTimeouts,columns=["timeout"])
faltTimeDF["label"] = faltTimeDF["timeout"].astype(str) + "s flat"

faltTimeDF["onTime"] = faltTimeDF.apply(lambda x: sum(obsDF.loc[obsDF["TTF"] < x.timeout]["TTF"]) + x.timeout*len(obsDF.loc[obsDF["TTF"] >= x.timeout]), axis=1)
faltTimeDF["successes"] = faltTimeDF.apply(lambda x: len(obsDF.loc[(obsDF["TTF"] <= x.timeout) & (obsDF["numSV"] > 4)]), axis=1)
schemeDFArr.append(faltTimeDF)


#calc on time and num successes for adaptive timeout options
adaptiveTimeouts = [[8,1,6]]
adaptTimeDF = pd.DataFrame(adaptiveTimeouts,columns=["timeout","step","min"])
adaptTimeDF["label"] = adaptTimeDF["timeout"].astype(str) + "s - " + adaptTimeDF["step"].astype(str) + "s to " + adaptTimeDF["min"].astype(str) + "s"

for index, row in adaptTimeDF.iterrows():
    obsDF["AT"+str(index)] = obsDF.apply(lambda x: currAdaptiveTimeout(x,row["timeout"],row["step"],row["min"]), axis=1)

adaptTimeDF["onTime"] = adaptTimeDF.apply(lambda x: sum(obsDF.loc[obsDF["TTF"] < obsDF["AT"+str(x.name)]]["TTF"]) + sum(obsDF.loc[obsDF["TTF"] >= obsDF["AT"+str(x.name)]]["AT"+str(x.name)]), axis=1)
adaptTimeDF["successes"] = adaptTimeDF.apply(lambda x: len(obsDF.loc[(obsDF["TTF"] <= obsDF["AT"+str(x.name)]) & (obsDF["numSV"] > 4)]), axis=1)
schemeDFArr.append(adaptTimeDF)


#calc on time and num successes for adaptive interval options
adaptiveTimeoutIntervals = [[6,1,5]]
adaptIntDF = pd.DataFrame(adaptiveTimeoutIntervals,columns=["timeout","skipStep","skipMax"])
adaptIntDF["label"] = adaptIntDF["timeout"].astype(str) + "s skip " + adaptIntDF["skipStep"].astype(str) + " to " + adaptIntDF["skipMax"].astype(str)

for index, row in adaptIntDF.iterrows():
    obsDF["AI"+str(index)] = obsDF.apply(lambda x: currAdaptiveInterval(x,row.timeout,row.skipStep,row.skipMax), axis=1)

adaptIntDF["onTime"] = adaptIntDF.apply(lambda x: sum(obsDF.loc[obsDF["TTF"] < obsDF["AI"+str(x.name)]]["TTF"]) + sum(obsDF.loc[obsDF["TTF"] >= obsDF["AI"+str(x.name)]]["AI"+str(x.name)]), axis=1)
adaptIntDF["successes"] = adaptIntDF.apply(lambda x: len(obsDF.loc[(obsDF["TTF"] <= obsDF["AI"+str(x.name)]) & (obsDF["numSV"] > 4)]), axis=1)
schemeDFArr.append(adaptIntDF)


#calc on time and num successes for adaptive timeout interval options
adaptiveTimeoutIntervals = [[8,1,6,1,5]]
adaptTimeIntDF = pd.DataFrame(adaptiveTimeoutIntervals,columns=["timeoutDef","timeoutStep","timeoutMin","skipStep","skipMax"])
adaptTimeIntDF["label"] = adaptTimeIntDF["timeoutDef"].astype(str) + "s - " + adaptTimeIntDF["timeoutStep"].astype(str) + "s to " \
      + adaptTimeIntDF["timeoutMin"].astype(str) + "s skip " + adaptTimeIntDF["skipStep"].astype(str) + " to " + adaptTimeIntDF["skipMax"].astype(str)

for index, row in adaptTimeIntDF.iterrows():
    obsDF["ATI"+str(index)] = obsDF.apply(lambda x: currAdaptiveTimeoutInterval(x,row.timeoutDef,row.timeoutStep,row.timeoutMin,row.skipStep,row.skipMax), axis=1)

adaptTimeIntDF["onTime"] = adaptTimeIntDF.apply(lambda x: sum(obsDF.loc[obsDF["TTF"] < obsDF["ATI"+str(x.name)]]["TTF"]) + sum(obsDF.loc[obsDF["TTF"] >= obsDF["ATI"+str(x.name)]]["ATI"+str(x.name)]), axis=1)
adaptTimeIntDF["successes"] = adaptTimeIntDF.apply(lambda x: len(obsDF.loc[(obsDF["TTF"] <= obsDF["ATI"+str(x.name)]) & (obsDF["numSV"] > 4)]), axis=1)
schemeDFArr.append(adaptTimeIntDF)


#merge all schemes and calc success rate and on time per fix
schemeDF = pd.concat(schemeDFArr)
schemeDF["successRate"] = (schemeDF["successes"]/len(obsDF["TTF"]))*100
schemeDF["onTimePerFix"] = schemeDF["onTime"]/schemeDF["successes"]


#plot schemes
fig, ax1 = plt.subplots()

plt.title("Timeout Scheme vs Performance")

x_labels = schemeDF["label"]
x_axis = np.arange(len(x_labels))
ax1.set_xticks(x_axis, x_labels)

col = "tab:red"
ax1.set_xlabel("Timeout Scheme")
ax1.set_ylabel("On time per fix (s)", color=col)
ax1.bar(x_axis-0.11, schemeDF["onTimePerFix"], width=0.2, color=col)
ax1.tick_params(axis="y", labelcolor=col)
ax1.set_ylim(0,None)

ax2 = ax1.twinx()

col = "tab:blue"
ax2.set_ylabel("Success Rate (%)", color=col)
ax2.bar(x_axis+0.11,schemeDF["successRate"], width=0.2, color=col)
ax2.tick_params(axis="y", labelcolor=col)
ax2.set_ylim(0,100)

plt.show()