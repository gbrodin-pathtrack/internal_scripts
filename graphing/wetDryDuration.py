import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join
import matplotlib.pyplot as plt

USE_PICKLE = True

if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"

immersionWantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_ImmersionAccel"+wantedExtension)]
immersionFileName = immersionWantedFiles[0]

if USE_PICKLE:
    df = pd.read_pickle(immersionFileName)
else:
    df = pd.read_csv(immersionFileName)

df.drop(df[df["year"] < 2024].index, inplace=True)

wetDryID = np.int64(0)
lastWetDry = 2

def genWetDryIDs(row):
    global wetDryID
    global lastWetDry

    if row.immersed != lastWetDry:
        wetDryID += np.int64(1)
    
    lastWetDry = row.immersed

    return wetDryID

# MIN_MONTH = 7
# MAX_MONTH = 5

# df.sort_values("datetime")
# df.drop(df[(df["month"] < MIN_MONTH) & (df["month"] > MAX_MONTH)].index, inplace=True)

tagIDs = df.tagID.unique()

for tagID in tagIDs:
    lastWetDry = 2
    df.loc[df["tagID"] == tagID, "wetDryID"] = df.loc[df["tagID"] == tagID].apply(genWetDryIDs, axis = 1)

df["wetDryID"] = df["wetDryID"].astype(int)

periods = df.groupby("wetDryID")

periodDF = pd.DataFrame({
    "tagID":periods["tagID"].first(),
    "datetime":periods["datetime"].first(),
    "year":periods["year"].first(),
    "month":periods["month"].first(),
    "day":periods["day"].first(),
    "immersed":periods["immersed"].first(),
    "duration":periods["immersed"].count(),
})

dryPeriodDF = periodDF[periodDF["immersed"] == 0]

def calcPossible(table, subSample):
    possibleNum = 0
    for dryDuration in range(1,subSample):
        possibleNum += len(table[table["duration"] == dryDuration]) * (dryDuration/subSample)
    
    possibleNum += len(table[table["duration"] >= subSample])

    return possibleNum

start = {}
end = {}
for tagID in tagIDs:
    tagDF = df[df["tagID"] == tagID]
    start[tagID] = tagDF["datetime"].min()
    end[tagID] = tagDF["datetime"].max()

tagMonths = dryPeriodDF.groupby(["tagID","year","month"])

tagMonthDF = pd.DataFrame({
    "tagID":tagMonths["tagID"].first(),
    "year":tagMonths["year"].first(),
    "month":tagMonths["month"].first(),
    "totalNum":tagMonths["duration"].count(),
    "possibleNum_2":tagMonths.apply(lambda x: calcPossible(x, 2)),
    "possibleNum_4":tagMonths.apply(lambda x: calcPossible(x, 4)),
    "possibleNum_10":tagMonths.apply(lambda x: calcPossible(x, 10)),
    "possibleNum_20":tagMonths.apply(lambda x: calcPossible(x, 20)),
})

tagMonthDF.reset_index(drop=True, inplace=True)

monthDays = [31,28,31,30,31,30,31,31,30,31,30,31]

def activeDays(row):
    global start
    global end
    global monthDays

    if row.year == start[row.tagID].year and row.month == start[row.tagID].month:
        return monthDays[int(row.month) - 1] - start[row.tagID].day + 1
    
    if row.year == end[row.tagID].year and row.month == end[row.tagID].month:
        return end[row.tagID].day

    return monthDays[int(row.month) - 1]

tagMonthDF["totalDays"] = tagMonthDF.apply(activeDays, axis=1)

tagMonthDF["1 min"] = tagMonthDF["totalNum"] / tagMonthDF["totalDays"]
tagMonthDF["2 min"] = tagMonthDF["possibleNum_2"] / tagMonthDF["totalDays"]
tagMonthDF["4 min"] = tagMonthDF["possibleNum_4"] / tagMonthDF["totalDays"]
tagMonthDF["10 min"] = tagMonthDF["possibleNum_10"] / tagMonthDF["totalDays"]
tagMonthDF["20 min"] = tagMonthDF["possibleNum_20"] / tagMonthDF["totalDays"]

months = tagMonthDF.groupby(["year","month"])

monthDF = pd.DataFrame({
    "year":months["year"].first(),
    "month":months["month"].first(),
    "1 min":months["1 min"].mean(),
    "2 min":months["2 min"].mean(),
    "4 min":months["4 min"].mean(),
    "10 min":months["10 min"].mean(),
    "20 min":months["20 min"].mean(),
})

monthDF.reset_index(drop=True, inplace=True)

monthDF.sort_values(["year","month"], inplace=True)

monthNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

monthDF["monthName"] = monthDF.apply(lambda x: monthNames[int(x.month)-1] + " " + str(int(x.year)), axis=1)

cols = ["1 min","4 min","10 min"]

x = np.arange(len(monthDF))

width = 1/(len(cols)+1)
mult = 0

fig, ax = plt.subplots()

for col in cols:
    offset = width * mult
    rects = ax.bar(x + offset, monthDF[col].values, width, label=col)
    ax.bar_label(rects, padding=3, fmt="%.1f")
    mult += 1

ax.set_ylabel("Wet to dry edges per day")
ax.set_title("Wet to dry edges per day per month at different sample rates")
ax.set_xticks(x + width*(len(cols)-1)/2, monthDF["monthName"])
ax.legend(loc="best")
plt.show()

# dryDurations = dryPeriodDF.duration.unique()

# dryDurations.sort()

# LIMIT = 10

# xLabels = []
# yValuesTypes = {"possible":[],"missed":[]}

# overLabel = ">="+str(LIMIT)
# overCount = 0

# for dryDuration in dryDurations:
#     num = len(dryPeriodDF[dryPeriodDF["duration"] == dryDuration])#*dryDuration
#     if dryDuration >= LIMIT:
#         overCount += num
#     else:
#         xLabels.append(str(dryDuration))
#         possibleNum = num * (dryDuration/(LIMIT))
#         yValuesTypes["missed"].append(num-possibleNum)
#         yValuesTypes["possible"].append(possibleNum)

# totalPossible = int(sum(yValuesTypes["possible"]) + overCount)
# totalMissed = int(sum(yValuesTypes["missed"]))

# yValuesTypes["possible = "+str(totalPossible)] = yValuesTypes.pop("possible")
# yValuesTypes["missed = "+str(totalMissed)] = yValuesTypes.pop("missed")

# plt.title("Distribution of durations of dry periods")
# plt.xlabel("Duration (num samples)")
# plt.ylabel("Count")

# bottom = np.zeros(len(xLabels))
# for type, yValueType in yValuesTypes.items():
#     plt.bar(xLabels, yValueType, label = type, bottom=bottom)
#     bottom += yValueType

# plt.bar(overLabel, overCount, color="tab:blue")

# plt.legend(loc="best")
# plt.show()