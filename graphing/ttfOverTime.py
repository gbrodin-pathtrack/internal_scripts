import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from os import listdir
from os.path import isfile, join

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
obsDF["time"] = pd.to_datetime(obsDF["time"])

plt.title("TTF stats over time")
plt.xlabel("Time")
plt.ylabel("TTF")
plt.plot(obsDF.time, obsDF.TTF)

plt.show()