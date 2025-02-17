import numpy as np

def parseInt32(data : np.ndarray) -> int:
    return data[0] + (data[1]<<8) + (data[2]<<16) + ((data[3]&0x7F)<<24) - ((data[3]&0x80)<<24)

def parseUInt32(data : np.ndarray) -> int:
    return data[0] + (data[1]<<8) + (data[2]<<16) + (data[3]<<24)

def parseInt16(data : np.ndarray) -> int:
    return data[0] + ((data[1]&0x7F)<<8) - ((data[1]&0x80)<<8)

def parseUInt16(data : np.ndarray) -> int:
    return data[0] + (data[1]<<8)
