import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from os import listdir
from os.path import isfile, join

USE_PICKLE = True

SMOOTHED = False

if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"
#get every file in root directory that ends with "_GPS"
wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_Accel"+wantedExtension)]

for fileName in wantedFiles:
    if USE_PICKLE:
        df = pd.read_pickle(fileName)
    else:
        df = pd.read_csv(fileName)

    tagID = fileName[-len("Tag61164_Accel.pkl"):-len("_Accel.pkl")]

    df["smoothed_mag"] = df["mag"].rolling(window=100, min_periods=0, center=True).mean()

    if SMOOTHED:
        plt.plot(df.time, df.smoothed_mag, label=tagID)
    else:
        plt.plot(df.time, df.mag, label=tagID)

plt.title("Acceleration Over Time")
plt.ylabel("Accel Magnitude (g)")
plt.xlabel("DateTime")
plt.legend(loc="best")
plt.show()