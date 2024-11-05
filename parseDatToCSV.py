import pandas as pd
import datetime
from os import listdir, remove
from os.path import isfile, join, exists

#set to True to combine all dat files to one CSV for processing together
combineFiles = True
#set to True if using packed time with subseconds
packedTime = False
#set to True if dopplerMS was recorded per sat
dopplerMS = True
#set to True if dopplerHz was recorded per sat
dopplerHz = True
#set to True to parse old GPS formated data
oldFormat = False

#set to GPS obs header byte (not used for old format)
OBS_LINE_HEADER_BYTE = 255

if oldFormat:
    packedTime = False
    dopplerMS = False
    dopplerHz = False

if packedTime:
    OBS_HEADER_LENGTH = 8
    OBS_NUM_SV_POS = 5
else:
    OBS_HEADER_LENGTH = 9
    OBS_NUM_SV_POS = 6  

OBS_SAT_LENGTH = 5
if dopplerMS:
    OBS_SAT_LENGTH += 4
if dopplerHz:
    OBS_SAT_LENGTH += 4

def parseObs(line, index, obsNum):
    #empty dict for obs info
    obs = {"obsNum":obsNum}
    #counters for number of each satelite type
    numGPS = 0
    numGalileo = 0
    numBeiDou = 0
    #get time tag out of obs
    if packedTime:
        obs["year"] = line[index] & 0x7F
        obs["month"] = ((line[index] & 0x80) >> 7) + ((line[index+1] & 0x05) << 1)
        obs["day"] = (line[index+1] & 0xF8) >> 3
        obs["hour"] = line[index+2] & 0x1F
        obs["minute"] = ((line[index+2] & 0xE0) >> 5) + ((line[index+3] & 0x07) << 3)
        obs["second"] = ((line[index+3] & 0xF8) >> 3) + ((line[index+4] & 0x01) << 5)
        obs["subsecond"] = (line[index+4] & 0xFE) >> 1
    else:
        obs["year"]=line[index] 
        obs["month"]=line[index+1]
        obs["day"]=line[index+2]
        obs["hour"]=line[index+3]
        obs["minute"]=line[index+4]
        obs["second"]=line[index+5]
        obs["subsecond"] = 0
    
    #convert time tag to datetime
    obs["datetime"] = datetime.datetime(year=2000+obs["year"], month=obs["month"], day=obs["day"], hour=obs["hour"], minute=obs["minute"], second=obs["second"], microsecond=15625*obs["subsecond"])

    #step past time tag
    index += OBS_NUM_SV_POS

    #get other info from obs header
    numSV = line[index]
    obs["numSV"] = numSV
    index += 1
    obs["vbatt"] = line[index]
    index += 1
    if oldFormat:
        #old format ttf is stored as seconds, any 0 second fixes are actually very close to 1 second
        obs["TTF"] = line[index]
        if obs["TTF"] == 0:
            obs["TTF"] = 1
    else:
        #new format ttf is stored as 10ths of seconds
        obs["TTF"] = line[index]/10
    index += 1

    #calculate end index of obs
    obsEnd = index + numSV*OBS_SAT_LENGTH
    #single sat with ID 0 to attach obs info to
    satArr = [{"ID":0}]
    #step through obs
    while index < obsEnd:
        #empty dict for sat info
        sat = {}
        #get info from sat, stepping index on
        sat["ID"] = line[index]
        index += 1
        if(1<=sat["ID"]<=32):
            numGPS += 1
        if(101<=sat["ID"]<=163):
            numBeiDou += 1
        if(201<=sat["ID"]<=236):
            numGalileo += 1
        sat["CNR"] = line[index]
        index += 1
        sat["codePhase"] = line[index] + line[index + 1]<<8 + line[index + 2]<<16
        index += 3
        if dopplerMS:
            sat["dopplerMS"] = line[index] + (line[index + 1]<<8) + (line[index + 2]<<16) + ((line[index + 3] & 0x7F)<<24) - ((line[index + 3] & 0x80)<<24)
            index += 4
        if dopplerHz:
            sat["dopplerHz"] = line[index] + (line[index + 1]<<8) + (line[index + 2]<<16) + ((line[index + 3] & 0x7F)<<24) - ((line[index + 3] & 0x80)<<24)
            index += 4
        #add sat info to array
        satArr.append(sat)

    #add counts for satelite types
    obs["numGPS"] = numGPS
    obs["numBeiDou"] = numBeiDou
    obs["numGalileo"] = numGalileo

    #attach obs info to each sat
    for sat in satArr:
        sat.update(obs)

    #return obs info and list of sat infos
    return satArr

#counter to give every observable in a file a unique number for easy processing
obsNum = 0

def parseDatFile(fileName, combine):
    #carry obsNum between runs so combined file gets all unique obs numbers
    global obsNum

    #keep copy of initial obs num
    obsNumOffset = obsNum

    #read whole file into string
    with open(fileName,"r") as f:
        fileString = f.read()

    #split file into lines
    lines = fileString.split("\n")
    #get data lines and split into bytes
    byteLines = [line.split() for line in lines if line[:1].isdigit()]
    #convert each byte from a string to number
    byteLines = [[int(byte) for byte in byteLine] for byteLine in byteLines]

    if oldFormat:
        gpsByteLines = [line for line in byteLines if line[0] in [0,1,2]]
    else:
        #get lines that start with gps header byte
        gpsByteLines = [line for line in byteLines if line[0] == OBS_LINE_HEADER_BYTE]

    #empty arrays for observable and satelite information
    satArr = []

    #for each gps line
    for line in gpsByteLines:
        #calculate length of data in line, big endian in old format, little endian otherwise
        if oldFormat:
            lineEnd = (line[0]<<8) + line[1]
        else:
            lineEnd = line[1] + (line[2]<<8)

        #empty array for indexes of observables in line
        obsIndexArr = []

        #starting index is 2 for old format, 3 otherwise
        if oldFormat:
            index = 2
        else:
            index = 3
        #step through line until the end
        while index < lineEnd:
            #append obs index
            obsIndexArr.append(index)
            #jump to end of this observable
            index += OBS_HEADER_LENGTH + OBS_SAT_LENGTH * line[index + OBS_NUM_SV_POS]
        
        #for each observable in the line
        for index in obsIndexArr:
            #parse out obs info and satelite info
            subSatArr = parseObs(line, index, obsNum)
            obsNum+= 1
            #add info to lists
            satArr.extend(subSatArr)
    
    #generate data frames of info and output to CSV for further processing
    satsDF = pd.DataFrame(satArr)

    #reorder columns a bit
    idCol = satsDF.pop("ID")
    satsDF.insert(satsDF.columns.get_loc("CNR"),"ID",idCol)
    datetimeCol = satsDF.pop("datetime")
    satsDF.insert(satsDF.columns.get_loc("obsNum")+1, "datetime", datetimeCol)

    #append to combined file, write in header if needed
    if combine:
        satsDF.to_csv("combined_sats.csv",mode="a",header=not exists("combined_sats.csv"),index=False)

    #subtract starting obsNum for the tag specific file
    satsDF["obsNum"] -= obsNumOffset
    #write to tag specific file
    satsDF.to_csv(fileName[:-4]+"_sats.csv",index=False)

#clear out old combined file
if exists("combined_sats.csv"):
    remove("combined_sats.csv")
            
#run parseDatFile on every file in root directory that starts with "Obs" and ends with ".dat"
onlyfiles = [f for f in listdir("./") if isfile(join("./", f)) and f.startswith("Obs") and f.endswith(".dat")]
for file in onlyfiles:
    #only produce a combined file if there are more than 1 dat files
    parseDatFile(file, len(onlyfiles)>1)