import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from os import listdir
from os.path import isfile, join

USE_PICKLE = True

SMOOTHED = False
SPLIT_AXES = False

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

    if SMOOTHED and SPLIT_AXES:
        df["smoothed_x"] = df["X"].rolling(window=100, min_periods=0, center=True).mean()
        df["smoothed_y"] = df["Y"].rolling(window=100, min_periods=0, center=True).mean()
        df["smoothed_z"] = df["Z"].rolling(window=100, min_periods=0, center=True).mean()
        plt.plot(df.datetime, df.smoothed_x, label=tagID+"_x")
        plt.plot(df.datetime, df.smoothed_y, label=tagID+"_y")
        plt.plot(df.datetime, df.smoothed_z, label=tagID+"_z")
    elif SMOOTHED:
        df["smoothed_mag"] = df["mag"].rolling(window=100, min_periods=0, center=True).mean()
        plt.plot(df.datetime, df.smoothed_mag, label=tagID)
    elif SPLIT_AXES:
        plt.plot(df.datetime, df.X, label=tagID+"_x")
        plt.plot(df.datetime, df.Y, label=tagID+"_y")
        plt.plot(df.datetime, df.Z, label=tagID+"_z")
    else:
        plt.plot(df.datetime, df.mag, label=tagID)

plt.title("Acceleration Over Time")
plt.ylabel("Accel Magnitude (g)")
plt.xlabel("DateTime")
plt.legend(loc="best")
plt.show()