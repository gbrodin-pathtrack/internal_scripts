#content = [0x0F, 0x00, 0x08, 0x00, 0x00, 0x08, 0x08, 0x00, 0x00]
content = [0x0e, 0x08]  

checkA = 0
checkB = 0

for byte in content:
    checkA += byte
    checkA &= 0xFF
    checkB += checkA
    checkB &= 0xFF

print("check sum:","0x{:02x}".format(checkA).upper().replace('X','x')+",","0x{:02x}".format(checkB).upper().replace('X','x'))