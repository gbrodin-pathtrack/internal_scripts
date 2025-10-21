from datetime import datetime, timedelta
import numpy as np
from parsers.parsePackedTime import parsePackedTimeZeroSS
from parsers.parseInt import parseUInt16


def parseImmersionLine(data : np.ndarray, commonHeader : np.ndarray, lineNum : int, mixed : bool) -> dict[str, list]:
    if mixed:
        raise ValueError("No mixed implementation for Immersion")
    
    interval = parseUInt16(data[:2])
    timeStep = timedelta(seconds=interval)

    obsArr = []

    index = 2
    while index < len(data):
        obsTime = parsePackedTimeZeroSS(data[index:])
        index += 5
        blockSamples = parseUInt16(data[index:])
        index += 2
        while blockSamples != 0:
            byteSamples = 8 if blockSamples > 8 else blockSamples
            immersionByte = data[index]
            for i in range(byteSamples):
                immersed = immersionByte & (0x1 << i) != 0
                obsArr.append({"line":lineNum,"datetime":obsTime,"immersed":immersed})
                obsTime += timeStep
            
            blockSamples -= byteSamples
            index += 1

    return{"Immersion":obsArr}