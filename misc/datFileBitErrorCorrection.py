from collections import Counter

INPUT_FILE_NAMES = [
    "Obs041125_155224_Tag49240.dat",
    "Obs041125_163950_Tag49240.dat",
    "Obs051125_092306_Tag49240.dat",
    "Obs051125_092511_Tag49240.dat",
    "Obs051125_092633_Tag49240.dat",
]

OUTPUT_NAME = "Fixed_Tag49240.dat"

inputFiles = []

for fileName in INPUT_FILE_NAMES:
    with open(fileName, 'r') as f:
        inputFiles.append(f.readlines())

numFiles = len(inputFiles)
if (numFiles % 2) != 1 or numFiles < 3:
    print("Need odd number of input files >= 3")
    exit(0)

numLines = len(inputFiles[0])
for inputLines in inputFiles:
    if len(inputLines) != numLines:
        print("All input files need same number of lines")
        exit(0)

outputFile = open(OUTPUT_NAME, 'w')

print("Processing")

numAgreed = [0 for i in range(numFiles)]

for lineNum in range(numLines):
    #non data lines just take line from first file
    if not inputFiles[0][lineNum][:1].isdigit():
        outputFile.write(inputFiles[0][lineNum])
        continue
    
    #get counts of each occurance
    counts = Counter([inputFiles[i][lineNum] for i in range(numFiles)])

    #take most common string and how many times it occured
    mostCommon, count = counts.most_common(1)[0]
    if count > numFiles // 2:
        outputFile.write(mostCommon)
    else:
        print("Skipped line",lineNum,"due to no consensus")

    for i in range(numFiles):
        if mostCommon == inputFiles[i][lineNum]:
            numAgreed[i] += 1

print("Done")
print(numAgreed)
outputFile.close()
