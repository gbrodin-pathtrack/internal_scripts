from os import listdir
from os.path import isfile, join

def processGSMLog(datFileName):
    prefix = "GSM"
    if any(tag in datFileName.lower() for tag in ("tag10204","tag10215","tag14114","tag14115","tag14121","tag14122","tag14297","tag14298","tag14299","tag14300")):
        prefix = "ONO"
    elif any(tag in datFileName.lower() for tag in ("tag14113","tag14113")):
        prefix = "NOSIM"
    elif any(tag in datFileName.lower() for tag in ("tag14180","tag14181","tag14182","tag14190","tag14191","tag14192")):
        prefix = "BS4G"
    outputFileName = prefix+datFileName[3:-4]+".txt"
    datFile = open(datFileName,"r")
    outputFile = open(outputFileName,"w",encoding="utf-8")
    text = datFile.read()
    commands = ""

    lines = text.split("\n")
    for line in lines:
        if line == "" or line[0:1].isnumeric() == False:
            continue
        line = line.split(" ")
        for num in line:
            try:
                if(int(num)) == 0:
                    break
                char = chr(int(num))
                if char != 'ÿ':
                    commands += char
            except:
                continue

    commands = commands.split("\n")
    for command in commands:
        if command.strip():
            outputFile.write(command)
    outputFile.close()
    datFile.close()

onlyfiles = [f for f in listdir("./") if isfile(join("./", f))]
for file in onlyfiles:
    if file.startswith("Obs") and file.endswith(".dat"):
        processGSMLog(file)