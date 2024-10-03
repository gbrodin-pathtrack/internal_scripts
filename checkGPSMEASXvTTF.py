datFile = open("Obs280524_144049_Tag58726.dat","r")
text = datFile.read()
lines = text.split('\n')
lines = [line for line in lines if line[0:1] in "012" and line != ""]
obsList = []
numWrong = 0
for line in lines:
    line = line.split(" ")
    numBytes = 256*int(line[0])+int(line[1])
    byteNum = 2
    while byteNum < numBytes:
        numSV = int(line[byteNum+6])
        obsList.append(line[byteNum:byteNum + numSV*5+9])
        byteNum+=numSV*5 + 9

for obs in obsList:
    if abs(int(obs[7]) - int(obs[8])*2) > 3:
        print(obs)


