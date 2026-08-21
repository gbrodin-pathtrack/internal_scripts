from datetime import datetime, timedelta

TICKS_PER_SECOND = 10_000_000
TICKS_PER_DAY = TICKS_PER_SECOND * 86400
DOTNET_EPOCH = datetime(1, 1, 1)


def parse64toDateTime(value : int) -> datetime:
    ticks = value & 0x3FFFFFFFFFFFFFFF

    return DOTNET_EPOCH + timedelta(microseconds=ticks // 10)