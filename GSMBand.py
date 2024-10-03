bands = "50862106"
bands = int(bands)
allowed = ""

for i in range(0,32):
    if bands % 2 == 1:
        allowed += "B"+str(i+1)+", "
    bands >>= 1

print(allowed)

bands = [2,4,5,26,25,13,12,20]
allowed = 0

for band in bands:
    allowed += 2**(band-1)

print(allowed)

print("****")

bands = "2"
bands = int(bands)
allowed = ""

for i in range(0,32):
    if bands % 2 == 1:
        allowed += "B"+str(i+65)+", "
    bands >>= 1

print(allowed)

bands = [66]
allowed = 0

for band in bands:
    allowed += 2**(band-65)

print(allowed)


