from datetime import datetime
from os import listdir
from os.path import isfile, join

def checkFile(fileName):
    print("*"*100)
    print(fileName)
    print()
    datFile = open(fileName,"r")
    text = datFile.read()
    lines = text.split('\n')
    numWrong = 0
    for i in range(len(lines)-2):
        if lines[i] == "" or lines[i][0:1].isnumeric() == False:
            continue
        line1 = lines[i].split(" ")
        line2 = lines[i+1].split(" ")
        time1 = datetime.strptime(" ".join(line1[:6]).split(".")[0], "%Y %m %d %H %M %S")
        time2 = datetime.strptime(" ".join(line2[:6]).split(".")[0], "%Y %m %d %H %M %S")
        # time1 = 60*int(line1[4]) + int(float(line1[5]))
        # time2 = 60*int(line2[4]) + int(float(line2[5]))
        diff = (time2 - time1).total_seconds()
        # if diff < 0:
        #     diff += 3600
        if diff > 90 or diff < 40:
            numWrong += 1
            print(diff, time2)
            # print(line1)
            # print(line2)
            # print()

    print("Number wrongly spaced:",numWrong)

onlyfiles = [f for f in listdir("./") if isfile(join("./", f))]
for file in onlyfiles:
    if file.startswith("Obs") and file.endswith("AccWetDry.txt"):
        checkFile(file)