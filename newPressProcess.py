#including libaries to read files and handle time
from datetime import datetime, timedelta
from os import listdir
from os.path import isfile, join

#function called for each dat file to be processed
def processFile(fileName):
    #open dat file to read
    datFile = open(fileName,"r")
    #open output file to write
    outFile = open(fileName[:-4]+"_Press_Temp.txt","w")
    #read dat file
    text = datFile.read()
    #split dat file into list of lines
    lines = text.split('\n')
    #filter to only lines with pressure data
    lines = [line for line in lines if line[0:2] == "10"]
    total = 0
    blocks = 0
    #loop for each line
    for line in lines:
        #split line up into individual bytes
        line = line.split(" ")
        #extract start time from header
        startTime = datetime.strptime(" ".join(line[4:10]), "%y %m %d %H %M %S")
        #extract elapsed time from header
        elapsedTime = int(line[10])*256+int(line[11])
        #extract alt obs index from header
        numBytes = int(line[2])*256+int(line[3])
        #initialise empty list for chunks to go into
        pressObsArr = []
        i = 12
        #keep track of number of pressure readings per line
        totalPressReadings = 0
        #loop through bytes in line
        while i < numBytes:
            #extract number of readings in chunk from chunk header
            numPressReadings = int(line[i])
            #add to total
            totalPressReadings += numPressReadings
            #split chunk out from line and add to list of chunks
            pressObsArr.append(line[i:i+numPressReadings*3+3])
            #step to next chunk
            i += numPressReadings*3+3
        
        #initialise empty list for individual readings
        pressTempArr = []
        #calc time interval between each reading
        timeInterval = timedelta(seconds=elapsedTime/totalPressReadings)
        #var to keep track of time for each reading
        currTime = startTime
        #loop for each chunk in list of chunks
        for obs in pressObsArr:
            #extract number of readings from chunk header
            numPressReadings = int(obs[0])
            #total += numPressReadings
            #blocks += 1
            #extract temperature from chunk header
            temp = int(obs[1]) + int(obs[2])*256
            if temp & 0x8000 == 0x8000:
                temp -= 65535
            temp /= 100
            #loop through bytes in chunk (3 per pressure reading)
            for i in range(3,numPressReadings*3+3,3):
                #extract pressure reading
                pressure = int(obs[i]) + int(obs[i+1])*256 + int(obs[i+2])*256*256
                pressure /= 4096
                #add pressure reading with time tag and temperature to list of readings
                pressTempArr.append({"Time":currTime,"Temp":temp,"Pressure":pressure})
                #step time on for next reading
                currTime = currTime + timeInterval
        #loop over each individual reading
        for pressTemp in pressTempArr:
            #format reading into string to be put into file
            outString = pressTemp["Time"].strftime("%y %m %d %H %M %S") + "    {:4.2f}".format(pressTemp["Temp"]) + "    {:6.2f}\n".format(pressTemp["Pressure"])
            #write reading to file
            outFile.write(outString)
    #close file to save
    outFile.close()
    #print(total/blocks)
        

#process all files in root directory that start with Obs, end with .dat and are from Tag1417X
onlyfiles = [f for f in listdir("./") if isfile(join("./", f))]
for file in onlyfiles:
    if file.startswith("Obs") and file.endswith(".dat") and any(tag in file for tag in ("Tag1417","Tag14199","Tag14200","Tag14201","Tag14202")):
        processFile(file)