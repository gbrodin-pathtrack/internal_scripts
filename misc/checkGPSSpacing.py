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
        time1 = int(float(line1[2]))
        time2 = int(float(line2[2]))
        diff = time2 - time1
        if diff < 0:
            diff += 86400
        if not (100 < diff < 150) and not (280 < diff < 380) and not (210 < diff < 260):
            numWrong += 1
            print(line1)
            print(line2)
            print(diff)
            print()

    print("Number wrongly spaced:",numWrong)

onlyfiles = [f for f in listdir("./") if isfile(join("./", f))]
for file in onlyfiles:
    if file.startswith("Obs") and file.endswith(".raw"):
        checkFile(file)