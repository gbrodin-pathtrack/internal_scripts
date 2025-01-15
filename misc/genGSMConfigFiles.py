from pathlib import Path

FIXED = 93
SOLAR_DRIVEN = 95
SOLAR_ASSIST = 97

#max 5 digits for any value
#UHF scaled by 30 sec
#comment out variables you don't want in the string
req_GPS_intv1 = 120
req_GPS_intv2 = 300
req_UHF_intv1 = 480
req_UHF_intv2 = 720
sched1_times = 0x000
# opmode1 = FIXED
# opmode2 = SOLAR_DRIVEN
# start_hour1 = 0
# start_hour2 = 6
# stop_hour1 = 24
# stop_stop2 = 18

dummy = True

tagPrefix = ""
tagIDsString = "10229-10277"

paramIDs = {
    'req_GPS_intv1':'42',
    'req_GPS_intv2':'43',
    'req_UHF_intv1':'44',
    'req_UHF_intv2':'45',
    'sched1_times':'48',
    'opmode1':'49',
    'opmode2':'50',
    'start_hour1':'51',
    'start_hour2':'52',
    'stop_hour1':'53',
    'stop_stop2':'54'
}
configString = ""

check = 0

for param in paramIDs:
    if param in locals():
        configString += paramIDs[param] +","
        configString += str(locals()[param]) +","
        check += locals()[param] &0xFF
        check += (locals()[param] >> 8) &0xFF
        check += int(paramIDs[param])

check += 41
configString += "41," +str(check)+","

if dummy:
    configString = "60,0,61,0,41,162,"

tagIDs = []
for tagID in tagIDsString.split(","):
    if "-" in tagID:
        for i in range(int(tagID.split("-")[0]),int(tagID.split("-")[1])+1):
            tagIDs.append(tagPrefix+str(i))
    else:
        tagIDs.append(tagPrefix+tagID)

print(configString)

Path("GSM_Configs").mkdir(exist_ok=True)

for tagID in tagIDs:
    with open("GSM_Configs/Tag"+tagID+"Config.bin","w") as f:
        f.write(configString)