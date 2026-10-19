from pathlib import Path
import re
import shutil
import struct
import tempfile

FIXD_HEADER = 0x46495844  # "FIXD", fixed data file
APND_HEADER = 0x41504E44  # "APND", expandable data file
FILE_VERSION = 1
COMPLETE_FLAG = 0x80

SUBTYPES = {".ptdl": ord("L"), ".ptdb": ord("B"), ".ptdw": ord("W")}
NO_SUBTYPE = 0


def read_exact(stream, count: int) -> bytes:
    data = stream.read(count)
    if len(data) != count:
        raise ValueError(f"Truncated file: expected {count} bytes, got {len(data)}")
    return data


def calc_crc(data: bytes) -> bytes:
    check_a = 0
    check_b = 0
    for b in data:
        check_a = (check_a + b) & 0xFF
        check_b = (check_b + check_a) & 0xFF
    return bytes([check_a, check_b])


def crc_ok(header: bytes, length: int) -> bool:
    """Check the CRC stored straight after the first length bytes of the header"""
    return len(header) >= length + 2 and calc_crc(header[:length]) == header[length:length + 2]


def replace_with_backup(file: Path, converted: Path, old_file: Path) -> None:
    file.rename(old_file)
    try:
        converted.replace(file)
    except OSError:
        old_file.rename(file)
        raise


def expandable_header(subtype_byte: int, line_length: int, dev_id: int, bytes_to_data: int) -> bytes:
    """Current 14 byte expandable header followed by its CRC"""
    header = struct.pack("<IBBHIH", APND_HEADER, FILE_VERSION, subtype_byte, line_length, dev_id, bytes_to_data)
    return header + calc_crc(header)


def dev_id_from_name(file: Path) -> int:
    """Files written before the header held the device ID are named yyMMdd_HHmmss_Tag<ID>.ptdw"""
    match = re.search(r"_Tag(\d+)\.ptdw$", file.name)
    if match is None or int(match.group(1)) > 0xFFFFFFFF:
        raise ValueError(f"Can't get device ID from file name: {file}")
    return int(match.group(1))


def convertFixed14(file: Path, old) -> bytes:
    """Fixed file with a 14 byte header (from 9 Sept 26), only the header value, subtype and complete flag change"""
    header = read_exact(old, 16)
    # Older files may have no subtype set, these take the subtype from their extension
    if header[5] != NO_SUBTYPE and header[5] != SUBTYPES[file.suffix]:
        raise ValueError(f"Subtype {header[5]:#04x} doesn't match extension: {file}")
    line_length, dev_id, bytes_to_data = struct.unpack_from("<HIH", header, 6)
    return expandable_header(SUBTYPES[file.suffix] | COMPLETE_FLAG, line_length, dev_id, bytes_to_data)


def convertFixed9(file: Path, old) -> bytes:
    """Fixed file with a 9 byte header (before 9 Sept 26), the device ID moves from the debug info to the header"""
    header = read_exact(old, 11)
    line_length, bytes_to_data = struct.unpack_from("<HH", header, 5)
    debug = read_exact(old, bytes_to_data)

    # Debug info: 5 padding, product (2), padding (2), version (4), device ID (4), used pages (4),
    # time (6), padding (9), partition count (1), then 16 bytes per partition
    if bytes_to_data < 37 or debug[:5] != bytes(5) or bytes_to_data != 37 + 16 * debug[36]:
        raise ValueError(f"Unexpected debug info in 9 byte header file: {file}")
    dev_id = struct.unpack_from("<I", debug, 13)[0]

    # Current debug info: product (2), padding (2), version (4), used pages (4), padding (4), then the rest as before
    new_debug = debug[5:13] + debug[17:21] + bytes(4) + debug[21:]
    return expandable_header(SUBTYPES[file.suffix] | COMPLETE_FLAG, line_length, dev_id, len(new_debug)) + new_debug


def convertWireless14(file: Path, old) -> bytes:
    """Expandable file with a 14 byte header from before subtypes, byte 5 only held the complete flag"""
    header = read_exact(old, 16)
    line_length, dev_id, bytes_to_data = struct.unpack_from("<HIH", header, 6)
    return expandable_header(SUBTYPES[file.suffix] | (COMPLETE_FLAG if header[5] else 0), line_length, dev_id, bytes_to_data)


def convertWireless10(file: Path, old) -> bytes:
    """Expandable file with a 10 byte header (before 9 Sept 26), with no device ID so it's taken from the file name"""
    header = read_exact(old, 12)
    line_length, bytes_to_data = struct.unpack_from("<HH", header, 6)
    return expandable_header(SUBTYPES[file.suffix] | (COMPLETE_FLAG if header[5] else 0), line_length,
                             dev_id_from_name(file), bytes_to_data)


def getConverter(file: Path, header: bytes):
    """Work out which layout the file has, returns None if already in the current format"""
    magic, version = struct.unpack_from("<IB", header)
    if version != FILE_VERSION:
        raise ValueError(f"Unknown file version {version}: {file}")

    # The version wasn't changed with the header layout, so the layout is found from where a valid CRC sits
    if magic == FIXD_HEADER and file.suffix in (".ptdl", ".ptdb"):
        layouts = {convertFixed14: crc_ok(header, 14), convertFixed9: crc_ok(header, 9)}
    elif magic == APND_HEADER:
        if crc_ok(header, 14) and header[5] & ~COMPLETE_FLAG == SUBTYPES[file.suffix]:
            return None
        if file.suffix != ".ptdw" or header[5] not in (0, 1):
            raise ValueError(f"Unexpected expandable data file: {file}")
        layouts = {convertWireless14: crc_ok(header, 14), convertWireless10: crc_ok(header, 10)}
    else:
        raise ValueError(f"Invalid data file header: {file}")

    matches = [converter for converter, valid in layouts.items() if valid]
    if len(matches) != 1:
        raise ValueError(f"{'No' if not matches else 'More than one'} header layout matches the CRC: {file}")
    return matches[0]


def convertDataFile(file: Path) -> bool:
    """Convert a data file to the current expandable format, returns False if already converted"""
    with file.open("rb") as old:
        header = old.read(16)
    if len(header) < 12:
        raise ValueError(f"Truncated file: {file}")

    converter = getConverter(file, header)
    if converter is None:
        return False

    oldFile = file.with_suffix(file.suffix + "_old")
    if oldFile.exists():
        raise FileExistsError(f"Backup already exists: {oldFile}")

    temp_file = None
    try:
        with file.open("rb") as old, tempfile.NamedTemporaryFile(
            mode="wb", dir=file.parent, prefix=file.name + ".", suffix=".tmp", delete=False
        ) as new:
            temp_file = Path(new.name)
            # Converter reads the old header (and debug info if it changes), the line data after it is kept as is
            new.write(converter(file, old))
            shutil.copyfileobj(old, new)

        replace_with_backup(file, temp_file, oldFile)
    finally:
        if temp_file is not None:
            temp_file.unlink(missing_ok=True)
    return True


root = Path.cwd()

for extension in SUBTYPES:
    for dataFile in root.rglob(f"*{extension}"):
        if convertDataFile(dataFile):
            print(f"Converted {dataFile}")
        else:
            print(f"Already converted {dataFile}")
