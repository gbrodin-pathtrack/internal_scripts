import datetime

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

def parsePressSingleLine(data, commonHeader, lineNum, outputArr):
    index = 0

    format = (data[0] & 0xF8) >> 3
    sensor = data[0] & 0x07
    index += 1    

    year = data[index] & 0x7F
    month = ((data[index] & 0x80) >> 7) + ((data[index+1] & 0x07) << 1)
    day = (data[index+1] & 0xF8) >> 3
    hour = data[index+2] & 0x1F
    minute = ((data[index+2] & 0xE0) >> 5) + ((data[index+3] & 0x07) << 3)
    second = ((data[index+3] & 0xF8) >> 3) + ((data[index+4] & 0x01) << 5)
    subsecond = (data[index+4] & 0xFE) >> 1
    index += 5

    startDatetime = datetime.datetime(year=2000+year, month=month, day=day, hour=hour, minute=minute, second=second)
    
    if format == 0:
        pressRaw = data[index] + (data[index+1]<<8)
        press = decode16BitPress(pressRaw, sensor)
        index += 2
        temp = ((data[index])*0.5)-40
        index += 1
        pressObs = {"line":lineNum,"headerTime":startDatetime,"datetime":startDatetime, "pressure":press,"temp":temp}
        outputArr.append(pressObs)
        
        while(index < len(data)):
            offset = data[index] + (data[index+1]<<8)
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
            offset = data[index] + (data[index+1] << 8)
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
            offset = data[index] + ((data[index+1] & 0x07)<<8)
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
            offset = data[index] + ((data[index+1] & 0x07)<<8)
            temp = (((((data[index+1]) & 0xF8)<<5) + data[index+2]) * 0.08) - 40
            index += 3
            obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
            
            pressObs = {"line":lineNum,"headerTime":startDatetime,"offset":offset,"datetime":obsDatetime,"temp":temp}
            outputArr.append(pressObs)
    
    if format == 4:
        interval = data[index]
        index += 1
        offset = 0           
        while(index < len(data)):
            offset += interval
            obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
            pressRaw = data[index] + (data[index+1]<<8)
            press = decode16BitPress(pressRaw, sensor)
            index += 2
            pressObs = {"line":lineNum,"datetime":obsDatetime, "pressure":press}
            outputArr.append(pressObs)