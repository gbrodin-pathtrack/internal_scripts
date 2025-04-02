from os import listdir
from os.path import isfile, join
import pandas as pd

USE_PICKLE = True

if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"
obsWantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_GPS_Obs"+wantedExtension) and "combined" not in f]
svWantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_GPS_SVs"+wantedExtension) and "combined" not in f]

#loop over wanted files and generate a combined version
if len(obsWantedFiles) > 1:
    dfArr = []
    for file in obsWantedFiles:
        if USE_PICKLE:
            df = pd.read_pickle(file)
        else:
            df = pd.read_csv(file)
        dfArr.append(df)
    df_combined = pd.concat(dfArr)
    df_combined.reset_index(inplace=True, drop=True)
    if USE_PICKLE:
        df_combined.to_pickle("combined_GPS_Obs.pkl")
    else:
        df_combined.to_csv("combined_GPS_Obs.csv",index=False)


#loop over wanted files and generate a combined version
if len(svWantedFiles) > 1:
    dfArr = []
    for file in svWantedFiles:
        if USE_PICKLE:
            df = pd.read_pickle(file)
        else:
            df = pd.read_csv(file)
        dfArr.append(df)
    df_combined = pd.concat(dfArr)
    df_combined.reset_index(inplace=True, drop=True)
    if USE_PICKLE:
        df_combined.to_pickle("combined_GPS_SVs.pkl")
    else:
        df_combined.to_csv("combined_GPS_SVs.csv",index=False)