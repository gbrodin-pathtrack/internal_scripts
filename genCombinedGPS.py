from os import listdir
from os.path import isfile, join
import pandas as pd

USE_PICKLE = True

if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"
wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_GPS"+wantedExtension) and not f.startswith("combined")]

#loop over wanted files and generate a combined version
if len(wantedFiles) > 1:
    dfArr = []
    for file in wantedFiles:
        if USE_PICKLE:
            df = pd.read_pickle(file)
        else:
            df = pd.read_csv(file)
        dfArr.append(df)
    df_combined = pd.concat(dfArr)
    if USE_PICKLE:
        df_combined.to_pickle("combined_GPS.pkl")
    else:
        df_combined.to_csv("combined_GPS.csv",index=False)

    wantedFiles.insert(0,"combined_GPS"+wantedExtension)