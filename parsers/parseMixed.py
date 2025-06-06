import numpy as np

from parsers.parsePressSingle import parsePressSingleLine
from parsers.parseImmersionAccel import parseImmersionAccelLine
from parsers.parseEHSolar import parseEHSolarLine
from parsers.parsePressureImmersion import parsePressureImmersionLine
from parsers.parseVedba import parseVeDBALine
from parsers.parsePressureSingleSemi import parsePressSingleSemiLine

TYPE_PARSERS = {
    0x01 : parsePressSingleLine,
    0x02 : parsePressSingleSemiLine,
    0x03 : parsePressureImmersionLine,
    0x04 : parseVeDBALine,
    0x05 : parseVeDBALine,
    0x06 : parseVeDBALine,
    0x07 : parseVeDBALine,
    # 0x08 : parseEHSolarLine,
    # 0x09 : parseImmersionAccelLine,
}

def parseMixedLine(data : np.ndarray, commonHeader : np.ndarray, lineNum : int, mixed : bool) -> dict[str, list]:
    if mixed:
        raise ValueError("No mixed implementation for Mixed")
    
    typeMap = data[0:4]
    intervals = data[4:7]

    lineParsedDataTypes: dict[str, list] = {}

    index = 7
    while index < len(data):
        blockTypeIndex = (data[index] & 0xC0) >> 6
        blockType = typeMap[blockTypeIndex]
        blockLen = data[index] & 0x3F

        if blockType not in TYPE_PARSERS.keys():
            if "Unknown_M" not in lineParsedDataTypes.keys():
                lineParsedDataTypes["Unknown_M"] = []
            lineParsedDataTypes["Unknown_M"].append(data[index : index + 50])
            index += 50
            continue

        blockParsedDataTypes = TYPE_PARSERS[blockType](data[index + 1: index + blockLen], np.array([blockType, intervals[blockTypeIndex]]), lineNum, True)

        for dataTypeStr, parsedData in blockParsedDataTypes.items():
            dataTypeStr += "_M"
            if dataTypeStr not in lineParsedDataTypes.keys():
                lineParsedDataTypes[dataTypeStr] = []
            lineParsedDataTypes[dataTypeStr].extend(parsedData)

        index += 50

    return lineParsedDataTypes