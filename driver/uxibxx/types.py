#TODO re-sort classes

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum, IntFlag
from typing import Literal


class UxibxxError(Exception):
    pass


class ConfigurationError(UxibxxError):
    pass


class InvalidArgument(UxibxxError):
    """
    What the name says.
    """
    pass


class UxibxxIoBoardError(UxibxxError):
    """
    Base class of all :class:`UxibxxIoBoard` errors
    """
    pass


class DeviceNotFound(UxibxxIoBoardError):
    """
    The UXIBxx board reported an error in response to a command.
    """
    pass


class ConnectionClosed(UxibxxIoBoardError):
    """
    This driver instance has already been deliberately closed and can no
    longer be used.
    """
    pass


class IdMismatch(UxibxxIoBoardError):
    """
    The model or board ID reported by the hardware doesn't match the expected
    or specified value
    """
    pass


class RemoteError(UxibxxIoBoardError):
    """
    The UXIBxx board reported an error in response to a command.
    """
    pass


class UnsupportedCommand(RemoteError):
    """
    The board didn't recognize the command -- likely either the driver class
    doesn't match the board model or the board is running a firmware variant
    that doesn't match the driver's expectations.
    """
    pass


class RemoteCommandNotImplemented(RemoteError):
    """
    The board reported that the command was recognized (i.e. the command
    mnemonic is listed as valid) but the corresponding functionality is not
    actually implemented in the firmware. This should not normally be seen on
    production firmware builds.
    """
    pass


class InvalidTerminalNo(UxibxxIoBoardError, ValueError):
    """
    The specified terminal number doesn't exist for the connected hardware.
    """
    pass


class ResponseTimeout(UxibxxIoBoardError):
    """
    A reponse line was not received within the prescribed time limit.
    """
    pass


class BadResponse(UxibxxIoBoardError):
    """
    The response from the hardware didn't align with the expected format.

    The most common situation where this is encountered is when accidentally
    connecting to a device that is not a UXIBxx board or is running an
    incompatible firmware.
    """
    pass


class Unsupported(UxibxxIoBoardError):
    """
    The specified terminal or channel doesn't support the requested action --
    for example, when attempting to set an output-only terminal to input mode.
    """
    pass


class InvalidState(UxibxxIoBoardError):
    pass


class VolMeasurementNotStarted(InvalidState):
    """
    There was an attempt to get the result of a volume measurement but no
    measurement was running on this channel.
    """
    pass


class IoDirection(Enum):
    """
    Identifies whether a given terminal logically acts as an "input" or
    an "output". The exact consequences in terms of electrical behavior depend
    on the hardware.

    For UXIB-DN12, terminals 13 and 14 (broken out on the extra headers on the
    bottoom of the board) are set to high-impedance in input mode and
    push-pull in output mode. Terminals 1-12 are open-collector outputs and
    only support output mode.
    """

    #: Terminal acts as an input
    INPUT = "in"

    #: Terminal acts as an output
    OUTPUT = "out"


_IoDirectionOrLiteral = IoDirection | Literal["in", "out"]


class FlowSampleFlags(IntFlag):
    AIR_IN_LINE = 1
    OVER_RANGE = 2


@dataclass(frozen=True)
class FlowRateHistoryRow:
    ml_per_min: float
    elapsed_s: float
    start_tick: int
    end_tick: int
    flags_occurred: FlowSampleFlags


@dataclass
class FlowRateHistoryResult:
    rows: list[FlowRateHistoryRow]
    n_dropped_before: int
    n_dropped_between: int
    # TODO: make it subscriptable + some convenience methods for dealing with the data


@dataclass(frozen=True)
class VolMeasurementResult:
    total_ml: float
    elapsed_s: float
    first_tick: int
    last_tick: int
    flags_occurred: FlowSampleFlags


class LeakDetectorStatus(IntFlag):
    NORMAL = 0,
    ACTIVE = 1,
    TRIGD = 2,
    SHORT = 0x10,
    OPEN = 0x20
    NODATA = 0x80


@dataclass(frozen=True)
class LeakDetectorRawReading:
    ab: int
    ba: int
    ts_tick: int


@dataclass(frozen=True)
class LeakDetectorResult:
    data_valid: bool
    status: LeakDetectorStatus
    ts_tick: int | None

    @property
    def status_name(self):
        return self.status.name

    @property
    def active(self):
        return self.data_valid and (self.status & LeakDetectorStatus.ACTIVE)

    @property
    def triggered(self):
        return self.data_valid and (self.status & LeakDetectorStatus.TRIGD)

    @property
    def faulted(self):
        return self.data_valid and (
            self.status & (LeakDetectorStatus.OPEN | LeakDetectorStatus.SHORT)
            )

    @classmethod
    def from_int(cls, int_val: int, ts_tick: int, data_valid: bool = True):
        return cls(
            data_valid = data_valid,
            ts_tick = ts_tick,
            status = LeakDetectorStatus(int_val)
            )


@dataclass(frozen=True)
class FlowSensorInfo:
    sensor_family: str # TODO figure out how we want to deal with this
    sensor_prod_id: str
    sensor_serial_no: str


@dataclass(frozen=True)
class FlowSampleRaw:
    flow_value: int
    ts_tick: int
    temp_value: int | None
    flags: FlowSampleFlags


@dataclass(frozen=True)
class FlowSample:
    ml_per_min: float
    ts_s: float
    temp_degc: float | None
    flags: FlowSampleFlags


class VolMeasurementResults:
    def __init__(self, data: Iterable[str, VolMeasurementResult]):
        self._data = dict(data)

    @property
    def total_ml(self) -> float:
        return self._get_result_attr("total_ml")

    @property
    def elapsed_s(self) -> float:
        return self._get_result_attr("elapsed_s")

    @property
    def first_tick(self) -> int:
        return self._get_result_attr("start_tick")

    @property
    def last_tick(self) -> int:
        return self._get_result_attr("end_tick")

    @property
    def flags_occurred(self) -> FlowSampleFlags:
        return FlowSampleFlags(0) # FIXME TODO return OR of all samples

    def items(self):
        return self._data.items()

    def __iter__(self):
        return iter(self._data)

    def __getitem__(self, key):
        return self._data[key]

    def _get_result_attr(self, attr_name: str):
        if len(self._data) > 1:
            ch_list_str = ",".join(self._data.keys())
            raise ValueError(
                f"Multiple channels ({ch_list_str}) in result set")
        value = None
        for result in self._data.values():
            value = getattr(result, attr_name)
            break
        return value
    

class _NoData(BaseException):
    pass
