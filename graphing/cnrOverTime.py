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
wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_GPS_SVs"+wantedExtension)]

fileName = wantedFiles[0]

#read file into data frame
if USE_PICKLE:
    svDF = pd.read_pickle(fileName)
else:
    svDF = pd.read_csv(fileName)
#convert datetime string to datetime
svDF["time"] = pd.to_datetime(svDF["time"])

aggregated = svDF.groupby("obsNum").agg(datetime = ("time","first"),max_cnr=("CNR","max"),min_cnr=("CNR","min"),avg_cnr=("CNR","mean"))
plt.title("CNR stats over time")
plt.xlabel("Time")
plt.ylabel("CNR")
#plt.plot(aggregated.datetime, aggregated.max_cnr,label="max")
#plt.plot(aggregated.datetime, aggregated.min_cnr,label="min")
plt.plot(aggregated.datetime, aggregated.avg_cnr,label="avg")
plt.legend(loc="best")

plt.show()