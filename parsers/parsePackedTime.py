from datetime import datetime

def parsePackedTime(timeArr):
    year = timeArr[0] & 0x7F
    month = ((timeArr[0] & 0x80) >> 7) + ((timeArr[1] & 0x07) << 1)
    day = (timeArr[1] & 0xF8) >> 3
    hour = timeArr[2] & 0x1F
    minute = ((timeArr[2] & 0xE0) >> 5) + ((timeArr[3] & 0x07) << 3)
    second = ((timeArr[3] & 0xF8) >> 3) + ((timeArr[4] & 0x01) << 5)
    subsecond = (timeArr[4] & 0xFE) >> 1

    return datetime(year=2000+year, month=month, day=day, hour=hour, minute=minute, second=second, microsecond=15625*subsecond)