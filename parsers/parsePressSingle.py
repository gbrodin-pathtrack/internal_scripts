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

def parsePressSingleLine(line, outputArr):
    index = 0

    format = (line[index] & 0xF8) >> 3
    sensor = line[index] & 0x07
    index += 1    

    year = line[index] & 0x7F
    month = ((line[index] & 0x80) >> 7) + ((line[index+1] & 0x07) << 1)
    day = (line[index+1] & 0xF8) >> 3
    hour = line[index+2] & 0x1F
    minute = ((line[index+2] & 0xE0) >> 5) + ((line[index+3] & 0x07) << 3)
    second = ((line[index+3] & 0xF8) >> 3) + ((line[index+4] & 0x01) << 5)
    subsecond = (line[index+4] & 0xFE) >> 1
    index += 5

    startDatetime = datetime.datetime(year=2000+year, month=month, day=day, hour=hour, minute=minute, second=second)

    if format == 0:
        pressRaw = line[index] + (line[index+1]<<8)
        press = decode16BitPress(pressRaw, sensor)
        index += 2
        temp = ((line[index])*0.5)-40
        index += 1
        pressObs = {"headerTime":startDatetime,"datetime":startDatetime, "pressure":press,"temp":temp}
        outputArr.append(pressObs)
        
        while(index < len(line)):
            offset = line[index] + (line[index+1]<<8)
            index += 2
            obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
            pressRaw = line[index] + (line[index+1]<<8)
            press = decode16BitPress(pressRaw, sensor)
            index += 2
            temp = ((line[index])*0.5)-40
            index += 1
            pressObs = {"headerTime":startDatetime,"offset":offset,"datetime":obsDatetime, "pressure":press,"temp":temp}
            outputArr.append(pressObs)

    if format == 1:
        if sensor != 0:
            print("Format 2 with non mini depth, can't process")
            return
        press = (line[index] * 40) + 1000
        index += 1
        pressObs = {"headerTime":startDatetime,"datetime":startDatetime, "pressure":press}
        outputArr.append(pressObs)
        
        while(index < len(line)):
            offset = line[index] + (line[index+1] << 8)
            index += 2
            obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
            press = (line[index] * 40) + 1000
            index += 1
            
            pressObs = {"headerTime":startDatetime,"offset":offset,"datetime":obsDatetime, "pressure":press}
            outputArr.append(pressObs)

    if format == 2:
        if sensor != 0:
            print("Format 3 with non mini depth, can't process")
            return
        press = (line[index] * 40) + 1000
        index += 1
        temp = subsecond
        pressObs = {"headerTime":startDatetime,"datetime":startDatetime, "pressure":press,"temp":temp}
        outputArr.append(pressObs)
        
        while(index < len(line)):
            offset = line[index] + ((line[index+1] & 0x07)<<8)
            temp = ((line[index+1]) & 0xF8)>>3
            index += 2
            obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
            press = (line[index] * 40) + 1000
            index += 1
            
            pressObs = {"headerTime":startDatetime,"offset":offset,"datetime":obsDatetime, "pressure":press,"temp":temp}
            outputArr.append(pressObs)
    
    if format == 3:
        temp = ((line[index] + (subsecond << 8)) * 0.08) - 40
        index += 1
        pressObs = {"headerTime":startDatetime,"datetime":startDatetime,"temp":temp}
        outputArr.append(pressObs)
        
        while(index < len(line)):
            offset = line[index] + ((line[index+1] & 0x07)<<8)
            temp = (((((line[index+1]) & 0xF8)<<5) + line[index+2]) * 0.08) - 40
            index += 3
            obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
            
            pressObs = {"headerTime":startDatetime,"offset":offset,"datetime":obsDatetime,"temp":temp}
            outputArr.append(pressObs)
    
    if format == 4:
        interval = line[index]
        index += 1
        offset = 0           
        while(index < len(line)):
            offset += interval
            obsDatetime = startDatetime + datetime.timedelta(seconds=offset)
            pressRaw = line[index] + (line[index+1]<<8)
            press = decode16BitPress(pressRaw, sensor)
            index += 2
            pressObs = {"datetime":obsDatetime, "pressure":press}
            outputArr.append(pressObs)