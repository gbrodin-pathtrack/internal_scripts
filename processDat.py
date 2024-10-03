import numpy as np
import matplotlib.pyplot as plt

datFile = open("Obs180624_152003_Tag14199.dat","r")
rawFile = open("30sec.raw","w")
daysOfMonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
text = datFile.read()
lines = text.split('\n')
#lines = ["1 254 23 10 20 11 33 8 7 0 4 32 41 39 131 12 31 41 61 82 14 29 43 23 85 4 28 40 189 85 5 25 41 78 34 23 12 42 43 198 17 11 43 100 100 25 23 10 20 11 33 39 6 0 5 32 43 185 182 4 31 41 115 22 3 29 42 58 71 25 28 39 220 186 26 12 41 26 43 10 11 41 102 141 15 23 10 20 11 34 9 7 0 4 32 41 147 139 1 31 41 76 150 28 29 41 107 244 18 28 39 110 216 20 25 39 222 218 9 12 41 43 47 7 11 40 125 104 10 23 10 20 11 34 40 7 0 4 32 42 154 201 13 31 41 43 111 5 29 43 158 252 27 28 41 72 82 30 25 40 217 240 20 12 43 198 155 19 11 42 117 164 20 23 10 20 11 35 11 6 0 4 32 42 4 11 21 31 42 98 74 9 29 41 124 7 0 25 40 47 10 27 12 42 135 11 27 11 41 10 229 25 23 10 20 11 35 42 7 0 4 32 41 247 72 9 31 41 86 32 26 29 42 177 13 17 28 40 190 71 20 25 40 226 31 14 12 42 238 118 15 11 41 226 33 12 23 10 20 11 36 13 7 0 5 12 41 104 222 31 32 41 145 131 25 31 41 16 226 6 29 42 104 2 30 28 40 106 176 1 25 40 58 45 29 11 43 15 83 26 23 10 20 11 36 44 7 0 4 32 41 54 106 9 31 40 212 106 19 29 42 175 188 10 28 39 156 219 14 25 39 43 240 11 12 40 237 239 15 11 41 126 65 8 23 10 20 11 37 14 7 0 4 25 40 152 3 19 32 42 193 165 17 31 41 80 57 24 29 42 148 190 15 28 41 166 79 20 12 41 248 85 24 11 39 25 125 14 23 10 20 11 37 45 7 0 4 32 43 47 114 5 31 41 235 149 8 29 42 175 79 0 28 40 160 83 5 25 40 205 166 5 12 42 79 76 12 11 42 232 72 0 23 10 20 11 38 16 6 0 4 32 41 146 158 30 31 40 153 82 30 29 40 73 65 22 28 38 242 183 27 25 40 135 171 29 12 39 211 161 5 23 10 20 11 38 47 6 0 4 31 39 119 16 13 29 41 16 53 5 28 39 128 30 11 25 40 36 178 14 12 40 86 249 23 11 41 192 167 7 255 255"]
obsDictArr = []
oldSeconds = -1
oldObs = ""
for line in lines:
    bytes = line.split(' ')
    if len(bytes) < 20 or bytes[0] == '6' or bytes[0] == '10':
        continue
    numBytes = int(bytes[0])*256+int(bytes[1])
    i = 2
    while i < numBytes:
        obsDict = dict()
        flag = 0
        year = 2000 + int(bytes[i])
        i += 1
        month = int(bytes[i])
        i += 1
        day = int(bytes[i])
        i += 1
        hours = int(bytes[i])
        i += 1
        mins = int(bytes[i])
        i += 1
        secs = int(bytes[i])
        i += 1
        numSV = int(bytes[i])
        i += 1
        batt = int(bytes[i])
        i += 1
        timeToFix = int(bytes[i])
        i += 1
        dayOfYear = sum(daysOfMonth[:month-1]) + day
        secondsOfDay = 3600*hours + 60*mins + secs
        obs = "%d %3d %5.1f %.2f %3d %2d " % (year,dayOfYear,secondsOfDay,batt,timeToFix,numSV)
        # if(oldSeconds>0):
        #     if(secondsOfDay-oldSeconds>50):
        #         print(oldObs)
        #         print(obs)                
        oldSeconds = secondsOfDay
        oldObs = obs
        numGal = 0
        numGPS = 0
        numGLO = 0
        numBei = 0
        numUnuseable = 0
        obsSVArr = []
        gpsCNRArr = []
        galCNRArr = []
        gloCNRArr = []
        beiCNRArr = []
        for j in range(0,numSV):
            svDict = dict()
            svID = int(bytes[i])
            i += 1
            cNR = int(bytes[i])
            i += 1
            if svID >= 100 and svID <= 140:
                flag = 1
                numGal += 1
                galCNRArr.append(cNR)
            elif svID <= 40:
                numGPS += 1
                gpsCNRArr.append(cNR)
            elif svID >= 150:
                numBei += 1
                beiCNRArr.append(cNR)
            elif svID >= 50 and svID <= 90:
                numGLO += 1
                gloCNRArr.append(cNR)
            if cNR < 30:
                numUnuseable += 1
            phase = int(bytes[i]) + int(bytes[i+1])*256 + int(bytes[i+2])*65536
            phase = phase * (2**-21)
            obs += "%3d %.10f 0 %2d" % (svID, phase, cNR)
            i += 3
            svDict["svID"] = svID
            svDict["CNR"] = cNR
            obsSVArr.append(svDict)
        obs += "32 32.0 32" + chr(10)
        obsDict["year"] = year
        obsDict["dayOfYear"] = dayOfYear
        obsDict["secondsOfDay"] = secondsOfDay
        obsDict["timeToFix"] = timeToFix
        obsDict["numSV"] = numSV
        obsDict["numGPS"] = numGPS
        obsDict["numGal"] = numGal
        obsDict["numGLO"] = numGLO
        obsDict["numBei"] = numBei
        obsDict["numUnuseable"] = numUnuseable
        obsDict["meanGPSCNR"] = np.NaN if len(gpsCNRArr) == 0 else np.mean(gpsCNRArr)
        obsDict["meanGalCNR"] = np.NaN if len(galCNRArr) == 0 else np.mean(galCNRArr)
        obsDict["meanGLOCNR"] = np.NaN if len(gloCNRArr) == 0 else np.mean(gloCNRArr)
        obsDict["meanBeiCNR"] = np.NaN if len(beiCNRArr) == 0 else np.mean(beiCNRArr)
        obsDict["svArr"] = obsSVArr
        obsDictArr.append(obsDict)
        if flag == 1:
            #print(obs)
            pass
        rawFile.write(obs)

ttfStr = ""
ttfStdStr = ""
numSVStr = ""
numSV90Str = ""
numSV10Str = ""
numSVStdStr = ""
numGPSStr = ""
numGalStr = ""
numGLOStr = ""
numBeiStr = ""
gpsCNRStr = ""
galCNRStr = ""
gloCNRStr = ""
beiCNRStr = ""
numUnStr = ""

oneSecData = 0
garyTTF = 0

if oneSecData == 1: 
    for start in range(0,8):
        end = np.floor_divide(len(obsDictArr),8) * 8
        step = 8

        nthObs = obsDictArr[start:end:step]

        galCNRArr = [obsDict["meanGalCNR"] for obsDict in nthObs]
        meanGalCNR = 0 if np.isnan(galCNRArr).all() else np.nanmean(galCNRArr)

        gpsCNRArr = [obsDict["meanGPSCNR"] for obsDict in nthObs]
        meanGPSCNR = 0 if np.isnan(gpsCNRArr).all() else np.nanmean(gpsCNRArr)

        gloCNRArr = [obsDict["meanGLOCNR"] for obsDict in nthObs]
        meanGLOCNR = 0 if np.isnan(gloCNRArr).all() else np.nanmean(gloCNRArr)

        beiCNRArr = [obsDict["meanBeiCNR"] for obsDict in nthObs]
        meanBeiCNR = 0 if np.isnan(beiCNRArr).all() else np.nanmean(beiCNRArr)

        numSVArr = [obsDict["numSV"] for obsDict in nthObs]

        ttfArr = [(obsDict["timeToFix"]/8) + 0.5 for obsDict in nthObs]

        ttfStr += "%.2f," % np.mean(ttfArr)
        ttfStdStr += "%.2f," % np.std(ttfArr)
        numSVStr += "%.2f," % np.mean(numSVArr)
        numSV90Str += "%.2f," % np.percentile(numSVArr,90)
        numSV10Str += "%.2f," % np.percentile(numSVArr,10)
        numSVStdStr += "%.2f," % np.std(numSVArr)
        numGPSStr += "%.2f," % np.mean([obsDict["numGPS"] for obsDict in nthObs])
        numGalStr += "%.2f," % np.mean([obsDict["numGal"] for obsDict in nthObs])
        numGLOStr += "%.2f," % np.mean([obsDict["numGLO"] for obsDict in nthObs])
        numBeiStr += "%.2f," % np.mean([obsDict["numBei"] for obsDict in nthObs])
        gpsCNRStr += "%.2f," % meanGPSCNR
        galCNRStr += "%.2f," % meanGalCNR
        gloCNRStr += "%.2f," % meanGLOCNR
        beiCNRStr += "%.2f," % meanBeiCNR
        numUnStr += "%.2f," % np.mean([obsDict["numUnuseable"] for obsDict in nthObs])

    print()
    print(ttfStr)
    print(ttfStdStr)
    print(numSVStr)
    print(numSV90Str)
    print(numSV10Str)
    print(numSVStdStr)
    #print(numGPSStr)
    #print(numGalStr)
    #print(numGLOStr)
    #print(numBeiStr)
    print(gpsCNRStr)
    #print(galCNRStr)
    #print(gloCNRStr)
    #print(beiCNRStr)
    print(numUnStr)
    print()

else:
    galCNRArr = [obsDict["meanGalCNR"] for obsDict in obsDictArr]
    meanGalCNR = 0 if np.isnan(galCNRArr).all() else np.nanmean(galCNRArr)

    gpsCNRArr = [obsDict["meanGPSCNR"] for obsDict in obsDictArr]
    meanGPSCNR = 0 if np.isnan(gpsCNRArr).all() else np.nanmean(gpsCNRArr)

    gloCNRArr = [obsDict["meanGLOCNR"] for obsDict in obsDictArr]
    meanGLOCNR = 0 if np.isnan(gloCNRArr).all() else np.nanmean(gloCNRArr)

    beiCNRArr = [obsDict["meanBeiCNR"] for obsDict in obsDictArr]
    meanBeiCNR = 0 if np.isnan(beiCNRArr).all() else np.nanmean(beiCNRArr)

    if garyTTF == 1:
        ttfArr = [1 if obsDict["timeToFix"] == 0 else obsDict["timeToFix"] + 0.5 for obsDict in obsDictArr]
    else:
        ttfArr = [(obsDict["timeToFix"]/2) + 0.5 for obsDict in obsDictArr]
    

    numSVArr = [obsDict["numSV"] for obsDict in obsDictArr]

    timeoutObs = [obsDict for obsDict in obsDictArr if obsDict["timeToFix"] == 60]
    print(timeoutObs)
    zeroSatObs = [obsDict for obsDict in obsDictArr if obsDict["numSV"] == 0]
    print(zeroSatObs)
    errorObs = [obsDict for obsDict in obsDictArr if obsDict["timeToFix"] == 250]
    print(errorObs)
    numDiff = 0
    timeDiffArr = []
    for i in range(len(obsDictArr)-1):
        timeA = obsDictArr[i]["secondsOfDay"] - obsDictArr[i]["timeToFix"]/2
        timeB = obsDictArr[i+1]["secondsOfDay"] - obsDictArr[i+1]["timeToFix"]/2
        if((63 < abs(timeA-timeB) or abs(timeA-timeB) < 57) and obsDictArr[i]["dayOfYear"] == obsDictArr[i+1]["dayOfYear"]): #32 < abs(timeA-timeB) or  
            numDiff += 1
            timeDiffArr.append(abs(timeA-timeB))
            print(abs(timeA-timeB))
            print(obsDictArr[i])
            print(obsDictArr[i+1])
            print()
    
    print(timeDiffArr)
    print("Num timeouts:", len(timeoutObs))
    print("Num not 60 sec appart:",numDiff)
    print("Average diff of non 60 sec type:",np.mean(timeDiffArr))

    print()
    print("Average time to fix:",np.mean(ttfArr))
    # print("Minimum time to fix:",np.min(ttfArr))
    print("90th percentile time to fix:",np.percentile(ttfArr,90))
    print("10th percentile time to fix:",np.percentile(ttfArr,10))
    print("Time to fix standard deviation:",np.std(ttfArr))
    print("Average num SVs:",np.mean(numSVArr))
    print("90th percentile num SVs:",np.percentile(numSVArr,90))
    print("10th percentile num SVs:",np.percentile(numSVArr,10))
    print("Standard deviation num SVs:",np.std(numSVArr))
    # print("Average num GPS:",np.mean([obsDict["numGPS"] for obsDict in obsDictArr]))
    # print("Average num gal:",np.mean([obsDict["numGal"] for obsDict in obsDictArr]))
    # print("Average num GLONASS:",np.mean([obsDict["numGLO"] for obsDict in obsDictArr]))
    # print("Average num BeiDou:",np.mean([obsDict["numBei"] for obsDict in obsDictArr]))
    print("Average GPS CNR:",meanGPSCNR)
    # print("Average Galileo CNR:",meanGalCNR)
    # print("Average GLONASS CNR:",meanGLOCNR)
    # print("Average BeiDou CNR:",meanBeiCNR)
    print("Average num unusable SVs:",np.mean([obsDict["numUnuseable"] for obsDict in obsDictArr]))
    print()


datFile.close()
rawFile.close()
