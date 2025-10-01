import pandas as pd
import numpy as np
from scipy.stats import pearsonr
import matplotlib.pyplot as plt
from os import listdir
from os.path import isfile, join

USE_PICKLE = True

SPLIT_PREV_FAIL = False

#0 = active points, 1 = max magnitude, 2 = min magnitude
TYPE = 2

if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"
#get every file in root directory that ends with "_GPS"
gpsWantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_GPS_Obs"+wantedExtension)]

gpsFileName = gpsWantedFiles[0]

#read file into data frame
if USE_PICKLE:
    obsDF = pd.read_pickle(gpsFileName)
else:
    obsDF = pd.read_csv(gpsFileName)
#convert datetime string to datetime
obsDF["datetime"] = pd.to_datetime(obsDF["datetime"])

accelWantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_Accel"+wantedExtension)]
accelFileName = accelWantedFiles[0]

if USE_PICKLE:
    accelDF = pd.read_pickle(accelFileName)
else:
    accelDF = pd.read_csv(accelFileName)

accelDF["burst"] = accelDF["datetime"].diff().dt.seconds.gt(180).cumsum()

accelBursts = accelDF.groupby("burst")

accelBurstDF = pd.DataFrame({
    "tagID":accelBursts["tagID"].first(),
    "datetime":accelBursts["datetime"].first(),
    "avgMag":accelBursts["mag"].mean(),
    "activePortion":accelBursts.apply(lambda burst: len(burst[(burst["mag"] < 0.8) | (burst["mag"] > 1.2)])*100/len(burst)),
    "maxMag":accelBursts["mag"].max(),
    "minMag":accelBursts["mag"].min(),
})

def getBurstID(obs):
    global accelBurstDF
    bursts = accelBurstDF.loc[(accelBurstDF["tagID"] == obs.tagID) & (accelBurstDF["datetime"] - obs.datetime < np.timedelta64(180))]
    if bursts.size == 0:
        return -1
    else:
        return bursts.tail(1).index[0]

obsDF["burstID"] = obsDF.apply(lambda obs: getBurstID(obs), axis=1)

obsDF = obsDF[obsDF.burstID != -1]

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
    if TYPE == 0:
        x = accelBurstDF.iloc[obsDF.burstID].activePortion
        y = obsDF.numSV
        plt.xlabel("Percentage of 'active' points (%)")
        plt.ylabel("Num SVs")
        plt.title("Accelerometer activity to GPS performance")
    elif TYPE == 1:
        x = accelBurstDF.iloc[obsDF.burstID].maxMag
        y = obsDF.numSV
        plt.xlabel("Maximum acceleration magnitude (g)")
        plt.ylabel("Num SVs")
        plt.title("Maximum magnitude to GPS performance")
    elif TYPE == 2:
        x = accelBurstDF.iloc[obsDF.burstID].minMag
        y = obsDF.numSV
        plt.xlabel("Minimum acceleration magnitude (g)")
        plt.ylabel("Num SVs")
        plt.title("Minimum magnitude to GPS performance")

    plt.scatter(x, y, marker='o', linewidth=0, alpha=0.5)
    plt.plot(np.unique(x), np.poly1d(np.polyfit(x, y, 1))(np.unique(x)),color="black",linestyle=(0,(5,7)),linewidth=1)
    plt.tight_layout()
    plt.show()

