import pandas as pd
import numpy as np
from scipy.stats import pearsonr
import matplotlib.pyplot as plt
from os import listdir
from os.path import isfile, join

USE_PICKLE = True

SPLIT_PREV_FAIL = True

if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"
#get every file in root directory that ends with "_GPS"
gpsWantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_GPS"+wantedExtension)]

gpsFileName = gpsWantedFiles[0]

#read file into data frame
if USE_PICKLE:
    fullDF = pd.read_pickle(gpsFileName)
else:
    fullDF = pd.read_csv(gpsFileName)
#convert datetime string to datetime
fullDF["fixTime"] = pd.to_datetime(fullDF["fixTime"])

#create new dataframe from rows with satelite ID of 0, these are dummy rows with only obs info attached
#obsDF = pd.DataFrame(fullDF.loc[fullDF["ID"] == 0]).reset_index(drop=True)
#drop sat info columns
#obsDF.drop([col for col in obsDF.columns if col in ["ID","CNR","codePhase","dopplerMS","dopplerHz"]],axis=1,inplace=True)
obsDF = fullDF

accelWantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_Accel"+wantedExtension)]
accelFileName = accelWantedFiles[0]

if USE_PICKLE:
    accelDF = pd.read_pickle(accelFileName)
else:
    accelDF = pd.read_csv(accelFileName)

accelDF["burst"] = accelDF["time"].diff().dt.seconds.gt(180).cumsum()

accelBursts = accelDF.groupby("burst")

accelBurstDF = pd.DataFrame({
    "tagID":accelBursts["tagID"].first(),
    "time":accelBursts["time"].first(),
    "avgMag":accelBursts["mag"].mean(),
    "activePortion":accelBursts.apply(lambda burst: len(burst[(burst["mag"] < 0.8) | (burst["mag"] > 1.2)])*100/len(burst))
})

obsDF["burstID"] = obsDF.apply(lambda obs: accelBurstDF.loc[(accelBurstDF["tagID"] == obs.tagID) & (accelBurstDF["time"] - obs.fixTime < np.timedelta64(180))].tail(1).index[0], axis=1)

if SPLIT_PREV_FAIL:
    obsDF["prevSuccess"] = (obsDF["numSV"].shift(1) > 4) # | (obsDF["numSV"].shift(2) > 4)
    obsDF.loc[[0],"prevSuccess"] = True

    prevSuccess = obsDF[obsDF["prevSuccess"] == True]
    prevFail = obsDF[obsDF["prevSuccess"] == False]

    x = accelBurstDF.iloc[prevSuccess.burstID].activePortion
    y = prevSuccess.numSV

    plt.scatter(x, y, marker='.', linewidth=0, alpha=0.1)
    plt.plot(np.unique(x), np.poly1d(np.polyfit(x, y, 1))(np.unique(x)),color="black",linestyle=(0,(5,7)),linewidth=1)
    plt.xlabel("Percentage of 'active' points (%)")
    plt.ylabel("Num SVs")
    plt.title("Accelerometer activity to GPS performance (prev success)")

    plt.figure()

    x = accelBurstDF.iloc[prevFail.burstID].activePortion
    y = prevFail.numSV

    plt.scatter(x, y, marker='.', linewidth=0, alpha=0.1)
    plt.plot(np.unique(x), np.poly1d(np.polyfit(x, y, 1))(np.unique(x)),color="black",linestyle=(0,(5,7)),linewidth=1)
    plt.xlabel("Percentage of 'active' points (%)")
    plt.ylabel("Num SVs")
    plt.title("Accelerometer activity to GPS performance (prev fail)")

    plt.show()
else:
    x = accelBurstDF.iloc[obsDF.burstID].activePortion
    y = obsDF.numSV

    plt.scatter(x, y, marker='.', linewidth=0, alpha=0.1)
    plt.plot(np.unique(x), np.poly1d(np.polyfit(x, y, 1))(np.unique(x)),color="black",linestyle=(0,(5,7)),linewidth=1)
    plt.xlabel("Percentage of 'active' points (%)")
    plt.ylabel("Num SVs")
    plt.title("Accelerometer activity to GPS performance")

    plt.show()

