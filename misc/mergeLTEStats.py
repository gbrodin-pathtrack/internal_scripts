from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib as plt
import shutil

# main_folder = Path("./z_keenan_lte")

# for folder in main_folder.glob("*_stats"):
#     if not folder.is_dir():
#         continue

#     uploads = folder / "uploads.csv"
#     failed_stats = folder / "failed_stats.csv"

#     if uploads.exists() and failed_stats.exists():
#         prefix = folder.name.removesuffix("_stats")

#         shutil.copy2(uploads, main_folder / f"{prefix}_uploads.csv")
#         shutil.copy2(failed_stats, main_folder / f"{prefix}_failed_stats.csv")

#         print(f"Copied {folder.name}")

for uploads_file in Path("./z_keenan_lte").glob("*_uploads.csv"):
    prefix = uploads_file.name.removesuffix("_uploads.csv")
    failed_file = Path(f"./z_keenan_lte/{prefix}_failed_stats.csv")

    if failed_file.exists():
        uploadsDF = pd.read_csv(uploads_file)
        failsDF = pd.read_csv(failed_file)
        uploadsDF["upload_time_utc"] = pd.to_datetime(uploadsDF["upload_time_utc"])
        failsDF["attempt_time_utc"] = pd.to_datetime(failsDF["attempt_time_utc"])
        uploadsDF["temp_time_utc"] = pd.to_datetime(uploadsDF["temp_time_utc"])
        failsDF["temp_time_utc"] = pd.to_datetime(failsDF["temp_time_utc"])

        uploadsDF.rename(columns={"upload_time_utc":"attempt_time_utc"}, inplace=True)

        attemptsDF = pd.concat([uploadsDF, failsDF])

        attemptsDF = attemptsDF[attemptsDF["vbatt (V)"].notna()]

        successRate = (len(attemptsDF[attemptsDF["data_summary"].notnull()])*100)/len(attemptsDF)
        psmPercent = (len(uploadsDF[uploadsDF["psm_ok"] == 1])*100)/len(uploadsDF)
        avgCon = np.mean(attemptsDF["connect (ms)"])
        avgSend = np.mean(attemptsDF["send (ms)"])
        avgTTFB = np.mean(attemptsDF["ttfb (ms)"])
        avgTX = np.mean(attemptsDF["tx_power (dBm)"])
        avgRX = np.mean(attemptsDF["rsrp (dBm)"])
        attemptsDF["battDiff"] = attemptsDF["vbatt (V)"] - (attemptsDF["modem_vbatt_mv"]/1000)
        avgBattDiff = np.mean(attemptsDF["battDiff"])
        minBattDiff = attemptsDF["battDiff"].min()
        maxBattDiff = attemptsDF["battDiff"].max()

        print(f"{prefix},{successRate},{psmPercent},{avgCon},{avgSend},{avgTTFB},{avgTX},{avgRX},{avgBattDiff},{minBattDiff},{maxBattDiff}")