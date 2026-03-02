QUIESCENT_CURRENT = 2 #uA
GPS_CURRENT = 10 #mA

SUCCESS_RATE = 0.591

SUCCESS_ON_TIME = 14.42
FAIL_ON_TIME = 23.59

NUM_RETRIES = [3,4]

INACTIVE_DAYS = 30

def onTime(retries):
    if retries == 0:
        return 0
    return SUCCESS_RATE * SUCCESS_ON_TIME + ((1-SUCCESS_RATE) * (FAIL_ON_TIME + onTime(retries-1)))

for numRetries in NUM_RETRIES:
    print("%d retries per day:" % numRetries)
    print("Probability of success per day: %.1f%%" % ((1 - (1-SUCCESS_RATE) ** numRetries) * 100))

    onTimePerDay = onTime(numRetries)

    print("On time per day: %.2fs" % onTimePerDay)

    gpsChargePerDay = GPS_CURRENT * onTimePerDay * (1000/3600) #uAh
    quiescentChargePerDay = QUIESCENT_CURRENT * 24

    print()

    for battery in (25, 40): #mAh
        charge = 1000 * battery
        charge -= INACTIVE_DAYS * quiescentChargePerDay
        days = charge / (gpsChargePerDay + quiescentChargePerDay)
        print("%dmAh battery expected to last %d days (~%.1f months)" % (battery, days, days/30.4))
    print()
