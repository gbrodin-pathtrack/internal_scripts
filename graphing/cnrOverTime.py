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

aggregated = fullDF.groupby("obsNum").agg(datetime = ("fixTime","first"),max_cnr=("CNR","max"),min_cnr=("CNR","min"),avg_cnr=("CNR","mean"))
plt.title("CNR stats over time")
plt.xlabel("Time")
plt.ylabel("CNR")
#plt.plot(aggregated.datetime, aggregated.max_cnr,label="max")
#plt.plot(aggregated.datetime, aggregated.min_cnr,label="min")
plt.plot(aggregated.datetime, aggregated.avg_cnr,label="avg")
plt.legend(loc="best")

plt.show()