import pandas as pd
import numpy as np
from scipy.stats import pearsonr
import matplotlib.pyplot as plt
from os import listdir
from os.path import isfile, join

USE_PICKLE = True

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

accelWantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_ImmersionAccel"+wantedExtension)]
accelFileName = accelWantedFiles[0]

if USE_PICKLE:
    accelDF = pd.read_pickle(accelFileName)
else:
    accelDF = pd.read_csv(accelFileName)

# def calcAngle(reading):
#     if reading.mag < 0.9 or reading.mag > 1.1:
#         return np.NaN
#     return np.degrees(np.arcsin(abs(reading.X)/reading.mag))

# accelDF["angle"] = accelDF.apply(lambda x: calcAngle(x), axis=1)

def getAngle(x):
    global accelDF
    diffs = accelDF[(accelDF["tagID"] == x.tagID)]["datetime"] - x.datetime
    idx = (diffs.abs()).idxmin()
    return np.mean(accelDF["angle"].iloc[idx-5:idx])

obsDF["angle"] = obsDF.apply(lambda x: getAngle(x), axis=1)

obsDF.dropna(subset=["angle"],inplace=True)

x = obsDF.angle
y = obsDF.numSV

plt.scatter(x, y, marker='o', linewidth=0, alpha=0.5)
plt.plot(np.unique(x), np.poly1d(np.polyfit(x, y, 1))(np.unique(x)),color="black",linestyle=(0,(5,7)),linewidth=1)
plt.xlabel("Angle between antenna and surface of earth (degrees)")
plt.ylabel("Num SVs")
plt.title("Device orientation to GPS performance")

plt.tight_layout()
plt.show()

