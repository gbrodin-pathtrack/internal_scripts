checkBytes = [0x44, 0x58, 0x49, 0x46, #FIXD
                             0x01, #Version 1
                             0x00, 0x02, #512 byte lines
                             0x05, 0x00, #num padding bytes
                             ]

checkA = 0
checkB = 0

for byte in checkBytes:
    checkA += byte
    checkA &= 0xFF
    checkB += checkA
    checkB &= 0xFF

print(f"Check A: 0x{checkA:X}, Check B: 0x{checkB:X}")
