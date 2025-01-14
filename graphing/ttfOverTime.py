import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from os import listdir
from os.path import isfile, join

#run processSatsFile on every file in root directory that ends with "_GPS.csv"
wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_GPS.csv")]

fileName = wantedFiles[0]

#read file into data frame
fullDF = pd.read_csv(fileName)
#convert datetime string to datetime
fullDF["fixTime"] = pd.to_datetime(fullDF["fixTime"])

#create new dataframe from rows with satelite ID of 0, these are dummy rows with only obs info attached
obsDF = pd.DataFrame(fullDF.loc[fullDF["ID"] == 0]).reset_index(drop=True)
#drop sat info columns
obsDF.drop([col for col in obsDF.columns if col in ["ID","CNR","codePhase","dopplerMS","dopplerHz"]],axis=1,inplace=True)

plt.title("TTF stats over time")
plt.xlabel("Time")
plt.ylabel("TTF")
plt.plot(obsDF.fixTime, obsDF.TTF)
plt.legend(loc="best")

plt.show()