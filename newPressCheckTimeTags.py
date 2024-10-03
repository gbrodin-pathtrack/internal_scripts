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
    lines = [line for line in lines if line[0:2] == "10"]
    numWrong = 0
    for i in range(len(lines)-1):
        line1 = lines[i].split(" ")
        line2 = lines[i+1].split(" ")
        time1 = datetime.strptime(" ".join(line1[4:10]), "%y %m %d %H %M %S")
        time2 = datetime.strptime(" ".join(line2[4:10]), "%y %m %d %H %M %S")
        calcDiff = time2 - time1
        calcDiff = calcDiff.total_seconds()
        storedDiff = int(line1[11])
        if calcDiff != storedDiff:
            numWrong += 1
            print(lines[i-1].split(" ")[4:12])
            print(line1[4:12])
            print(line2[4:12])
            print()

    print(numWrong)

onlyfiles = [f for f in listdir("./") if isfile(join("./", f))]
for file in onlyfiles:
    if file.startswith("Obs") and file.endswith(".dat") and any(tag in file for tag in ("Tag1417","Tag14199","Tag14200","Tag14201","Tag14202")):
        checkFile(file)