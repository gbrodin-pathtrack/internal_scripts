import datetime
import numpy as np
from parsers.parsePackedTime import parsePackedTimeZeroSS

def decode16BitPress(value, sensor):
    if sensor == 0: #mini depth
        return value * 0.5
    elif sensor == 1: #mini alt
        return value * 0.02
    elif sensor == 2: #large com
        if value <= 55500:
            return value * 0.02
        else:
            return value-55500

def parsePressSingleLine(data : np.ndarray, commonHeader : np.ndarray, lineNum : int, mixed : bool) -> dict[str, list]:
    #mixed and non mixed identical

    outputArr = []

    format = (data[0] & 0xF8) >> 3
    sensor = data[0] & 0x07

    startDatetime = parsePackedTimeZeroSS(data[1:6])
    subsecond = (data[5] & 0xFE) >> 1

    index = 6
    
    if format == 0:
        pressRaw = data[index] + (data[index+1]<<8)
        press = decode16BitPress(pressRaw, sensor)
        index += 2
        temp = ((data[index])*0.5)-40
        index += 1
        pressObs = {"line":lineNum,"headerTime":startDatetime,"datetime":startDatetime, "pressure":press,"temp":temp}
        outputArr.append(pressObs)
        
        while(index < len(data)):
            offset = int(data[index]) + (int(data[index+1])<<8)
            index += 2
            obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
            pressRaw = data[index] + (data[index+1]<<8)
            press = decode16BitPress(pressRaw, sensor)
            index += 2
            temp = ((data[index])*0.5)-40
            index += 1
            pressObs = {"line":lineNum,"headerTime":startDatetime,"offset":offset,"datetime":obsDatetime, "pressure":press,"temp":temp}
            outputArr.append(pressObs)

    if format == 1:
        if sensor != 0:
            print("Format 2 with non mini depth, can't process")
            return
        press = (data[index] * 40) + 1000
        index += 1
        pressObs = {"line":lineNum,"headerTime":startDatetime,"datetime":startDatetime, "pressure":press}
        outputArr.append(pressObs)
        
        while(index < len(data)):
            offset = int(data[index]) + (int(data[index+1]) << 8)
            index += 2
            obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
            press = (data[index] * 40) + 1000
            index += 1
            
            pressObs = {"line":lineNum,"headerTime":startDatetime,"offset":offset,"datetime":obsDatetime, "pressure":press}
            outputArr.append(pressObs)

    if format == 2:
        if sensor != 0:
            print("Format 3 with non mini depth, can't process")
            return
        press = (data[index] * 40) + 1000
        index += 1
        temp = subsecond
        pressObs = {"line":lineNum,"headerTime":startDatetime,"datetime":startDatetime, "pressure":press,"temp":temp}
        outputArr.append(pressObs)
        
        while(index < len(data)):
            offset = int(data[index]) + ((int(data[index+1]) & 0x07)<<8)
            temp = ((data[index+1]) & 0xF8)>>3
            index += 2
            obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
            press = (data[index] * 40) + 1000
            index += 1
            
            pressObs = {"line":lineNum,"headerTime":startDatetime,"offset":offset,"datetime":obsDatetime, "pressure":press,"temp":temp}
            outputArr.append(pressObs)
    
    if format == 3:
        temp = ((data[index] + (subsecond << 8)) * 0.08) - 40
        index += 1
        pressObs = {"line":lineNum,"headerTime":startDatetime,"datetime":startDatetime,"temp":temp}
        outputArr.append(pressObs)
        
        while(index < len(data)):
            offset = int(data[index]) + ((int(data[index+1]) & 0x07)<<8)
            temp = (((((data[index+1]) & 0xF8)<<5) + data[index+2]) * 0.08) - 40
            index += 3
            obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
            
            pressObs = {"line":lineNum,"headerTime":startDatetime,"offset":offset,"datetime":obsDatetime,"temp":temp}
            outputArr.append(pressObs)
    
    if format == 4 or format == 5:
        interval = int(subsecond)
        tempFlag = False
        if format == 5:
            tempFlag = True
            temp = ((data[index])*0.5)-40
            index += 1
        offset = 0
        while(index < len(data)):
            obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
            pressRaw = data[index] + (data[index+1]<<8)
            press = decode16BitPress(pressRaw, sensor)
            index += 2
            pressObs = {"line":lineNum,"datetime":obsDatetime, "pressure":press}
            if tempFlag:
                tempFlag = False
                pressObs["temp"] = temp
            outputArr.append(pressObs)
            #pressObs["raw"] = pressRaw
            offset += interval

    return {"PressSingle":outputArr}