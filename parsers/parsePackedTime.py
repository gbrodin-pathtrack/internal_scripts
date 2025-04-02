from datetime import datetime

def validateTime(year, month, day, hour, minute, second, subsecond):
    errorStr = ""
    error = False
    if year > 99:
        error = True
        errorStr += "Year invald %d " % year
    if month < 1 or month > 12: 
        error = True
        errorStr += "Month invald %d " % month
    if day < 1 or day > 31:
        error = True
        errorStr += "Day invald %d " % day
    if hour > 23:
        error = True
        errorStr += "Hour invald %d " % hour
    if minute > 59:
        error = True
        errorStr += "Minute invald %d " % minute
    if second > 59:
        error = True
        errorStr += "Second invald %d " % second
    if subsecond > 63:
        error = True
        errorStr += "Subsecond invald %d " % subsecond
    
    if error:
        raise ValueError(errorStr)

def parsePackedTime(timeArr):
    year = timeArr[0] & 0x7F
    month = ((timeArr[0] & 0x80) >> 7) + ((timeArr[1] & 0x07) << 1)
    day = (timeArr[1] & 0xF8) >> 3
    hour = timeArr[2] & 0x1F
    minute = ((timeArr[2] & 0xE0) >> 5) + ((timeArr[3] & 0x07) << 3)
    second = ((timeArr[3] & 0xF8) >> 3) + ((timeArr[4] & 0x01) << 5)
    subsecond = (timeArr[4] & 0xFE) >> 1

    validateTime(year, month, day, hour, minute, second, subsecond)

    return datetime(year=2000+year, month=month, day=day, hour=hour, minute=minute, second=second, microsecond=15625*subsecond)

def parsePackedTimeZeroSS(timeArr):
    year = timeArr[0] & 0x7F
    month = ((timeArr[0] & 0x80) >> 7) + ((timeArr[1] & 0x07) << 1)
    day = (timeArr[1] & 0xF8) >> 3
    hour = timeArr[2] & 0x1F
    minute = ((timeArr[2] & 0xE0) >> 5) + ((timeArr[3] & 0x07) << 3)
    second = ((timeArr[3] & 0xF8) >> 3) + ((timeArr[4] & 0x01) << 5)

    validateTime(year, month, day, hour, minute, second, 0)

    return datetime(year=2000+year, month=month, day=day, hour=hour, minute=minute, second=second)
