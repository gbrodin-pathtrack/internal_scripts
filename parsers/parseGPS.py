import datetime

#ADC ref is 1V, 8bit scale = 255 divisions, voltage read is 1/5 of actual vbatt so * 5
VBATT_SCALE = (5/255)

obsNum = 0

def validateTimeTag(obs):
    ret = True
    if(obs["year"] > 99):
        print("ERROR: Year not in 0-99")
        print("Year:",obs["year"])
        ret = False
    if(obs["month"] > 12 or obs["month"] == 0):
        print("ERROR: Month not in 1-12")
        print("Month:",obs["month"])
        ret = False
    if(obs["day"] > 31 or obs["day"] == 0):
        print("ERROR: Day not in 1-31")
        print("Day:",obs["day"])
        ret = False
    if(obs["hour"] > 23):
        print("ERROR: Hour not in 0-23")
        print("Hour:",obs["hour"])
        ret = False
    if(obs["minute"] > 59):
        print("ERROR: Minute not in 0-59")
        print("Minute:",obs["minute"])
        ret = False
    if(obs["second"] > 59):
        print("ERROR: Second not in 0-59")
        print("Second:",obs["second"])
        ret = False
    if(obs["subsecond"] > 63):
        print("ERROR: Subsecond not in 0-63")
        print("Subsecond:",obs["subsecond"])
        ret = False
    return ret

def parseObs(line, index):
    global obsNum
    #empty dict for obs info
    obs = {"obsNum":obsNum}
    obsNum += 1
    #counters for number of each satelite type
    numGPS = 0
    numGalileo = 0
    numBeiDou = 0
    #get time tag out of obs
    obs["year"] = line[index] & 0x7F
    obs["month"] = ((line[index] & 0x80) >> 7) + ((line[index+1] & 0x07) << 1)
    obs["day"] = (line[index+1] & 0xF8) >> 3
    obs["hour"] = line[index+2] & 0x1F
    obs["minute"] = ((line[index+2] & 0xE0) >> 5) + ((line[index+3] & 0x07) << 3)
    obs["second"] = ((line[index+3] & 0xF8) >> 3) + ((line[index+4] & 0x01) << 5)
    obs["subsecond"] = (line[index+4] & 0xFE) >> 1
    
    #convert time tag to datetime
    if(validateTimeTag(obs)):
        obs["fixTime"] = datetime.datetime(year=2000+obs["year"], month=obs["month"], day=obs["day"], hour=obs["hour"], minute=obs["minute"], second=obs["second"], microsecond=15625*obs["subsecond"])
    else:
        print("WARNING: Invalid time found")

    #step past time tag
    index += 5

    #get other info from obs header
    numSV = line[index]
    obs["numSV"] = numSV
    index += 1
    obs["vbatt"] = line[index] * VBATT_SCALE
    index += 1
    #ttf is stored in 10ths of seconds
    obs["TTF"] = line[index]/10
    index += 1

    #calculate end index of obs
    obsEnd = index + numSV*5
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
    return satArr, index

def parseGPSLine(data, commonHeader, outputArr):
    index = 0
    while index < len(data):
        newSats, index = parseObs(data, index)
        outputArr.extend(newSats)