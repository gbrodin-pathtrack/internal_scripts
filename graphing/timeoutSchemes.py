import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from os import listdir
from os.path import isfile, join

consecutiveTimeouts = 0
prevTimedOut = False
def currAdaptiveTimeout(obs, timeout, step, min):
    global consecutiveTimeouts
    global prevTimedOut

    if prevTimedOut:
        consecutiveTimeouts += 1

    currTimeout = max(min, timeout-step*consecutiveTimeouts)

    if obs.TTF >= currTimeout:
        prevTimedOut = True
    else:
        prevTimedOut = False
        consecutiveTimeouts = 0
    return currTimeout
        

USE_PICKLE = True

if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"
#get every file in root directory that ends with "_GPS"
wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_GPS"+wantedExtension)]

fileName = wantedFiles[0]

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

schemeDFArr = []

#calc on time and num successes for flat timeout options
flatTimeouts = [12,5]
flatDF = pd.DataFrame(flatTimeouts,columns=["timeout"])
flatDF["label"] = flatDF["timeout"].astype(str) + "s flat"

flatDF["onTime"] = flatDF.apply(lambda x: sum(obsDF.loc[obsDF["TTF"] < x.timeout]["TTF"]) + x.timeout*len(obsDF.loc[obsDF["TTF"] >= x.timeout]), axis=1)
flatDF["successes"] = flatDF.apply(lambda x: len(obsDF.loc[(obsDF["TTF"] <= x.timeout) & (obsDF["numSV"] > 4)]), axis=1)
schemeDFArr.append(flatDF)


#calc on time and num successes for adaptive timeout options
adaptiveTimeouts = [[12,2,5],[7,1,5]]
adaptiveDF = pd.DataFrame(adaptiveTimeouts,columns=["timeout","step","min"])
adaptiveDF["label"] = adaptiveDF["timeout"].astype(str) + "s - " + adaptiveDF["step"].astype(str) + "s to " + adaptiveDF["min"].astype(str) + "s"

for index, row in adaptiveDF.iterrows():
    obsDF["AT"+str(index)] = obsDF.apply(lambda x: currAdaptiveTimeout(x,row["timeout"],row["step"],row["min"]), axis=1)

adaptiveDF["onTime"] = adaptiveDF.apply(lambda x: sum(obsDF.loc[obsDF["TTF"] < obsDF["AT"+str(x.name)]]["TTF"]) + sum(obsDF.loc[obsDF["TTF"] >= obsDF["AT"+str(x.name)]]["AT"+str(x.name)]), axis=1)
adaptiveDF["successes"] = adaptiveDF.apply(lambda x: len(obsDF.loc[(obsDF["TTF"] <= obsDF["AT"+str(x.name)]) & (obsDF["numSV"] > 4)]), axis=1)
schemeDFArr.append(adaptiveDF)


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
ax1.bar(x_axis-0.1, schemeDF["onTimePerFix"], width=0.1, color=col)
ax1.tick_params(axis="y", labelcolor=col)
ax1.set_ylim(0,None)

ax2 = ax1.twinx()

col = "tab:blue"
ax2.set_ylabel("Success Rate (%)", color=col)
ax2.bar(x_axis+0.1,schemeDF["successRate"], width=0.1, color=col)
ax2.tick_params(axis="y", labelcolor=col)
ax2.set_ylim(0,100)

plt.show()