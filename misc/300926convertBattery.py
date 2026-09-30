from pathlib import Path
import struct
import tempfile


def read_exact(stream, count: int) -> bytes:
    data = stream.read(count)
    if len(data) != count:
        raise ValueError(f"Truncated file: expected {count} bytes, got {len(data)}")
    return data


def battery_bytes(voltage_bytes: bytes) -> bytes:
    voltage = struct.unpack("<d", voltage_bytes)[0]
    raw_battery = round((voltage * 50) - 1)
    return struct.pack("<BB", raw_battery, 1)  # AVR_LIPO


def replace_with_backup(file: Path, converted: Path, old_file: Path) -> None:
    file.rename(old_file)
    try:
        converted.replace(file)
    except OSError:
        old_file.rename(file)
        raise


def convertPtraw(file: Path):
    oldFile = file.with_suffix(".ptraw_old")
    if oldFile.exists():
        raise FileExistsError(f"Backup already exists: {oldFile}")

    temp_file = None
    try:
        with file.open("rb") as old, tempfile.NamedTemporaryFile(
            mode="wb", dir=file.parent, prefix=file.name + ".", suffix=".tmp", delete=False
        ) as new:
            temp_file = Path(new.name)
            header = read_exact(old, 6)
            if header[:4] != b"WRTP" or header[4] != 1:
                raise ValueError(f"Invalid .ptraw header: {file}")
            new.write(header)
            new.write(read_exact(old, header[5]))  # Source filename

            while timestamp := old.read(8):
                if len(timestamp) != 8:
                    raise ValueError(f"Truncated .ptraw timestamp: {file}")
                battery = battery_bytes(read_exact(old, 8))
                ttf_and_count = read_exact(old, 5)
                satellites = read_exact(old, ttf_and_count[4] * 10)
                new.write(timestamp + battery + ttf_and_count + satellites)

        replace_with_backup(file, temp_file, oldFile)
    finally:
        if temp_file is not None:
            temp_file.unlink(missing_ok=True)


def convertPtproc(file: Path):
    oldFile = file.with_suffix(".ptproc_old")
    if oldFile.exists():
        raise FileExistsError(f"Backup already exists: {oldFile}")

    temp_file = None
    try:
        with file.open("rb") as old, tempfile.NamedTemporaryFile(
            mode="wb", dir=file.parent, prefix=file.name + ".", suffix=".tmp", delete=False
        ) as new:
            temp_file = Path(new.name)
            header = read_exact(old, 8)
            if header != b"PTPROC-1":
                raise ValueError(f"Invalid .ptproc header: {file}")
            new.write(header)

            while timestamp := old.read(8):
                if len(timestamp) != 8:
                    raise ValueError(f"Truncated .ptproc timestamp: {file}")
                fields = read_exact(old, 40)  # Processed time, position, residual
                battery = battery_bytes(read_exact(old, 8))
                num_sv = read_exact(old, 4)
                new.write(timestamp + fields + battery + num_sv)

                while True:
                    parameter = read_exact(old, 4)
                    kind, length = struct.unpack("<HH", parameter)
                    if kind == 0 and length != 0:
                        raise ValueError(f"Invalid .ptproc end parameter: {file}")
                    new.write(parameter + read_exact(old, length))
                    if kind == 0:
                        break

        replace_with_backup(file, temp_file, oldFile)
    finally:
        if temp_file is not None:
            temp_file.unlink(missing_ok=True)


root = Path.cwd()

for ptraw in root.rglob("*.ptraw"):
    convertPtraw(ptraw)

for ptproc in root.rglob("*.ptproc"):
    convertPtproc(ptproc)
