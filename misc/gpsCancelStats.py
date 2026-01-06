import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join

USE_PICKLE = True

if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"

gpsWantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_GPS_Obs"+wantedExtension)]

gpsFileName = gpsWantedFiles[0]

#read files into data frames
if USE_PICKLE:
    obsDF = pd.read_pickle(gpsFileName)
else:
    obsDF = pd.read_csv(gpsFileName)

obsDF["cancelledZero"] = obsDF["numSV"] == 0
obsDF["cancelledWet"] = (obsDF["numSV"] > 0) & (obsDF["numSV"] < 5) & (obsDF["TTF"] < 20)

obsDF["cancelled"] = obsDF["cancelledZero"] | obsDF["cancelledWet"]
obsDF["saved"] = 20 - obsDF["TTF"]

print("Percent cancelled zero: %d%%" % ((len(obsDF.loc[obsDF["cancelledZero"] == True]) / len(obsDF)) * 100))
print("Percent cancelled wet: %d%%" % ((len(obsDF.loc[obsDF["cancelledWet"] == True]) / len(obsDF)) * 100))
print("Average cancel saving: %.2fs" % obsDF.loc[obsDF["cancelled"] == True, "saved"].mean())
print("Success rate of non cancelled: %d%%" % ((len(obsDF.loc[(obsDF["numSV"] >= 5) & (obsDF["cancelled"] == False)]) / len(obsDF.loc[obsDF["cancelled"] == False])) * 100))