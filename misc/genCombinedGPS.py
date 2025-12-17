from os import listdir
from os.path import isfile, join
import pandas as pd

USE_PICKLE = True

ROOT = "./"

if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"
obsWantedFiles = [f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.endswith("_GPS_Obs"+wantedExtension) and "combined" not in f]
obsIMWantedFiles = [f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.endswith("_GPS_IM_Obs"+wantedExtension) and "combined" not in f]
svWantedFiles = [f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.endswith("_GPS_SVs"+wantedExtension) and "combined" not in f]

#loop over wanted files and generate a combined version
if len(obsWantedFiles) > 1:
    dfArr = []
    for file in obsWantedFiles:
        if USE_PICKLE:
            df = pd.read_pickle(ROOT+file)
        else:
            df = pd.read_csv(ROOT+file)
        dfArr.append(df)
    df_combined = pd.concat(dfArr)
    df_combined.reset_index(inplace=True, drop=True)
    if USE_PICKLE:
        df_combined.to_pickle(ROOT+"combined_GPS_Obs.pkl")
    else:
        df_combined.to_csv(ROOT+"combined_GPS_Obs.csv",index=False)

#loop over wanted files and generate a combined version
if len(obsIMWantedFiles) > 1:
    dfArr = []
    for file in obsIMWantedFiles:
        if USE_PICKLE:
            df = pd.read_pickle(ROOT+file)
        else:
            df = pd.read_csv(ROOT+file)
        dfArr.append(df)
    df_combined = pd.concat(dfArr)
    df_combined.reset_index(inplace=True, drop=True)
    if USE_PICKLE:
        df_combined.to_pickle(ROOT+"combined_GPS_IM_Obs.pkl")
    else:
        df_combined.to_csv(ROOT+"combined_GPS_IM_Obs.csv",index=False)


#loop over wanted files and generate a combined version
if len(svWantedFiles) > 1:
    dfArr = []
    for file in svWantedFiles:
        if USE_PICKLE:
            df = pd.read_pickle(ROOT+file)
        else:
            df = pd.read_csv(ROOT+file)
        dfArr.append(df)
    df_combined = pd.concat(dfArr)
    df_combined.reset_index(inplace=True, drop=True)
    if USE_PICKLE:
        df_combined.to_pickle(ROOT+"combined_GPS_SVs.pkl")
    else:
        df_combined.to_csv(ROOT+"combined_GPS_SVs.csv",index=False)