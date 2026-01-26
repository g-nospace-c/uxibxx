from collections.abc import Iterable, Callable
from enum import Enum
import logging
import re

import serial
import serial.tools.list_ports

from . import types
from . import features
from .usb_ids import USB_VIDPID_FOR_MODEL



logger = logging.getLogger(__name__)



def get_driver_info_for_usb_vidpid(vid: int, pid: int):
    model_name, driver_cls = _driver_info_for_vidpid.get(
        (vid, pid), (None, None))
    return (model_name, driver_cls or UxibxxIoBoard)


def get_driver_class_for_usb_vidpid(vid: int, pid: int):
    model_name, driver_cls = get_driver_info_for_usb_vidpid(vid, pid)
    return driver_cls


def get_model_name_for_usb_vidpid(vid: int, pid: int):
    model_name, driver_cls = get_driver_info_for_usb_vidpid(vid, pid)
    return model_name


# TODO consider checking model name string when initializing a board-specific
# driver
class UxibxxIoBoardBase:
    """
    Common communications driver class for controlling UXIBxx I/O boards.
    """
    SERIAL_TIMEOUT_S = 1.

    UxibxxIoBoardError = types.UxibxxIoBoardError
    DeviceNotFound = types.DeviceNotFound
    IdMismatch = types.IdMismatch
    ResponseTimeout = types.ResponseTimeout
    Unsupported = types.Unsupported
    RemoteError = types.RemoteError
    UnsupportedCommand = types.UnsupportedCommand
    RemoteCommandNotImplemented = types.RemoteCommandNotImplemented
    BadResponse = types.BadResponse
    ConnectionClosed = types.ConnectionClosed

    _mnem_terminator_pat = re.compile(r"[?=:]+")

    def __init__(self, ser_port: serial.Serial,
                 board_model: str | None = None,
                 board_id: str | None = None,
                 info_usb_loc: str = "???",
                 info_usb_vidpid: tuple[int, int] | None = None):
        """
        :param ser_port: a ``serial.Serial`` instance that will be used to
            communicate with the hardware
        :param board_model: If not ``None``, this will be checked against the
            board model string reported by the hardware and :exc:`IdMismatch`
            will be raised in case of a mismatch
        :param board_id: Same as ``board_model`` but for the board ID string
        """
        if hasattr(ser_port, 'timeout'):
            ser_port.timeout = self.SERIAL_TIMEOUT_S
        self._ser_port = ser_port
        if hasattr(self._ser_port, 'port'):
            self._portname = self._ser_port.port
            if any(x is None for x in [info_usb_loc, info_usb_vidpid]):
                found_usb_loc, found_usb_vidpid = \
                    self._get_usb_info_for_portname(self._portname)
                info_usb_loc = (
                    found_usb_loc
                    if info_usb_loc is None
                    else info_usb_loc
                    )
                info_usb_vidpid = (
                    found_usb_vidpid
                    if info_usb_vidpid is None
                    else info_usb_vidpid
                    )
        else:
            self._portname = "???"

        self._usb_loc = info_usb_loc
        self._usb_vidpid = info_usb_vidpid
        self._update_ident_info()
        self._hrt_interval_s = None
        if self.remote_api_ver >= (3, 1):
            tick_freq, tick_counter_size, hrt_freq, \
                hrt_counter_size = self._get_tick_info()
            self._tick_counter_mod = 2**tick_counter_size
            if hrt_counter_size < 0:
                # HRT resets with gen tick rollover
                self._hrt_counter_mod = (
                    self._tick_counter_mod * 10**(-hrt_counter_size))
            else:
                self._hrt_counter_mod = 2**hrt_counter_size
        else:
            # hardcoded values for older FW
            tick_freq = 1000.
            self._tick_counter_mod = 0x10000
            hrt_freq = None
            self._hrt_counter_mod = None
        self._seconds_per_tick = 1. / tick_freq
        if hrt_freq:
            self._hrt_interval_s = 1. / hrt_freq
        for (desc, expected, actual) in [
                ("board model", board_model, self.board_model),
                ("board ID", board_id, self.board_id),
                ]:
            if expected is None:
                continue
            if expected != actual:
                raise self.IdMismatch(
                    f"Wrong {desc} (expected {expected!r}, "
                    f"board reported {actual!r}) for device on "
                    f"port {self._portname!r}"
                    )
        self._feature_names = set()
        super().__init__()

    def _add_feature_name(self, name: str):
        self._feature_names.add(name)

    @classmethod
    def list_connected_devices(
            cls, usb_vidpid: tuple[int, int] | None = None,
            ext_info: bool = False  # Off by default for compatibility
            ) -> list[
            tuple[str, str | None] | tuple[
                str, str | None, tuple[int, int] | None]  # jeez
            ]:
        """
        Get a list of all connected UXIBxx devices. Detection is based on the
        USB vendor ID, product ID and serial number descriptors reported by the
        OS. This method does not attempt to open the devices or verify that
        they are actually accessible.

        Only supported on Windows, macOS and Linux.

        :param usb_vidpid: A tuple ``(vid, pid)`` specifying a particular
            USB vendor and product ID to look for instead of using the default
            list of IDs.
        :param ext_info: See below.
        :returns: If ``ext_info=True``, a list of tuples of the form
            ``(portname, location, board_id, (vid, pid), model_name)`` where:
            ``portname`` is a string used by pySerial to identify the port,
            ``location`` is a USB port location,
            ``board_id`` is the board ID string reported by the hardware,
            ``vid`` and ``pid`` are the USB VID and PID respectively as
            integers, and
            ``model_name`` is the model name reported by the hardware.
            Otherwise, a list of tuples ``(vid, pid)`` only.

        """
        usb_vidpids = (
            [tuple(usb_vidpid)] if usb_vidpid is not None
            else set(cls.USB_VIDPIDS)
            )
        return [
            (
                (
                    info.device,
                    info.location,
                    info.serial_number,
                    (info.vid, info.pid),
                    get_model_name_for_usb_vidpid(info.vid, info.pid) or "???"
                    )
                if ext_info
                else (info.device, info.serial_number)
                )
            for info in serial.tools.list_ports.comports()
            if (info.vid, info.pid) in usb_vidpids
            ]

    @classmethod
    def _get_usb_info_for_portname(cls, portname: str):
        for \
            found_portname, usb_loc, board_id_, found_vidpid, model_name \
            in cls.list_connected_devices(ext_info=True):
                if found_portname == portname:
                    return usb_loc, found_vidpid
        return None, None

    @classmethod
    def _select_and_open(
            cls,
            usb_vidpid: tuple[int, int] | None = None,
            board_model: str | None = None,
            board_id: str | None = None,
            serial_portname: str | None = None,
            **kwargs
            ):
        for portname, usb_loc, board_id_, found_vidpid, model_name \
                    in cls.list_connected_devices(
                        usb_vidpid=usb_vidpid, ext_info=True):
            if board_id is not None and board_id != board_id_:
                continue
            if serial_portname is not None and serial_portname != portname:
                continue
            driver_cls = (
                get_driver_class_for_usb_vidpid(*found_vidpid)
                if cls is UxibxxIoBoard and found_vidpid is not None
                else cls
                )
            return driver_cls.from_serial_portname(
                portname,
                board_model=board_model,
                board_id=board_id,
                info_usb_loc=usb_loc,
                info_usb_vidpid=found_vidpid,
                no_usb_lookup=True,
                **kwargs
                )
        filter_desc = ", ".join(
            f"{name}={value!r}"
            for name, value in [
                ('usb_vidpid', usb_vidpid),
                ('board_id', board_id)
                ]
            if value is not None
            )
        raise cls.DeviceNotFound(
            f"No {cls.__name__} device(s) found"
            + (f" matching {filter_desc}" if filter_desc else "")
            )

    @classmethod
    def open_first_device(
            cls,
            usb_vidpid: tuple[int, int] | None = None,
            **kwargs) -> 'UxibxxIoBoard':
        """
        Opens the first device found. Intended for convenience in situations
        where only one candidate device is connected.

        If called on the base class, will dispatch to a model-specific class
        appropriate for the found device if possible. If called on a
        model-specific class, will only look for devices of that model
        (based on USB VID/PID).

        :param usb_vidpid: A tuple ``(vid, pid)`` specifying a particular
            USB vendor and product ID to look for instead of using the default
            list of IDs.
        :param kwargs: keyword arguments to pass to :meth:`__init__`
        :raises DeviceNotFound: If no matching devices were found
        :raises serial.SerialException: If something went wrong opening the
            serial device
        """
        return cls._select_and_open(usb_vidpid=usb_vidpid, **kwargs)

    @classmethod
    def from_board_id(cls, board_id: str, **kwargs) -> 'UxibxxIoBoard':
        """
        Finds and opens the UXIBxx device matching the specified board ID,
        if present.

        If called on the base class, will dispatch to a model-specific class
        appropriate for the found device if possible. If called on a
        model-specific class, will only look for devices of that model
        (based on USB VID/PID).

        :param board_id: board ID string of the hardware to connect to
        :param kwargs: keyword arguments to pass to :meth:`__init__`
        :returns: New :class:`UxibxxIoBoard` instance
        :raises DeviceNotFound: If no matching devices were found
        :raises serial.SerialException: If something went wrong opening the
            serial device
        """
        return cls._select_and_open(board_id=board_id, **kwargs)

    @classmethod
    def _open_serial_port(cls, portname: str):
        return serial.Serial(portname, timeout=cls.SERIAL_TIMEOUT_S)

    @classmethod
    def from_serial_portname(cls, portname: str, *args,
                             no_usb_lookup: bool = False,
                             require_usb_lookup: bool = False, **kwargs):
        """
        Opens and configures the serial port identified by ``portname`` and
        uses it to initialize a new :class:`UxibxxIoBoard` instance.

        :param portname: Port name or URL to pass to ``serial.Serial()``
        :param kwargs: keyword arguments to pass to :meth:`__init__`
        :returns: New :class:`UxibxxIoBoard` instance
        :raises serial.SerialException: If something went wrong opening the
            serial device
        """
        if not no_usb_lookup:
            try:
                return cls._select_and_open(
                    *args, serial_portname=portname, **kwargs)
            except cls.DeviceNotFound:
                if require_usb_lookup:
                    raise
        ser = cls._open_serial_port(portname)
        return cls(ser, *args, **kwargs)

    def _read_response_line(self):
        response = self._ser_port.readline().decode('ascii')
        logger.debug("Response: " + repr(response))
        if not response.endswith("\n"):
            raise self.ResponseTimeout()
        return response.strip()

    def _read_response(self, mnem_was: str):
        response = self._read_response_line()
        if response == "ND":
            raise types._NoData()
        elif response.startswith("ERROR"):
            reason = response.split(":", 1)[-1]
            if reason == "CMD":
                raise self.UnsupportedCommand(
                    f"Board doesn't support command: {mnem_was!r}")
            elif reason == "IMP":
                raise self.RemoteCommandNotImplemented(
                    f"Board reports command {mnem_was!r} is recognized but "
                    "not implemented"
                    )
            # TODO handle more error codes
            raise self.RemoteError(response)
        return response

    def _write_cmd_and_get_response(self, cmd: str, append: str = ""):
        mnem = self._mnem_terminator_pat.split(cmd, 1)[0]
        cmd_msg = f"{cmd}{append}\r".encode('ascii')
        logger.debug("Cmd msg out: " + repr(cmd_msg))
        self._ser_port.write(cmd_msg)
        return mnem, self._read_response(mnem_was=mnem)

    def ask_raw(self, text: str):
        cmd_msg = text.strip().encode('ascii') + b"\r"
        logger.debug("Raw msg out: " + repr(cmd_msg))
        self._ser_port.write(cmd_msg)
        return self._read_response_line()

    def _ask(self, cmd: str, resp_fields: Iterable[Callable] = (str,), n_resp_fields: int | None = None):
        if n_resp_fields is None:
            n_resp_fields = len(resp_fields)
        mnem, response = self._write_cmd_and_get_response(cmd, append="?")
        if "=" not in response:
            raise self.BadResponse("No = symbol in response?")
        left, right = response.rsplit("=", 1)
        if left.split(":", 1)[0] != mnem:
            raise self.BadResponse(
                "Left side of response doesn't match the command? "
                f"(expected {mnem!r}, got {left!r})"
                )
        resp_fields = list(resp_fields)
        ans_pieces = right.split(",", n_resp_fields - 1)
        if len(ans_pieces) != len(resp_fields):
            raise self.BadResponse(
                "Wrong number of answer fields in response ()"
                f"(expected {len(resp_fields)}, got {len(ans_pieces)})"
                )
        returnees = []
        for i, conv_fn in enumerate(resp_fields):
            try:
                conv_val = conv_fn(ans_pieces[i].strip())
            except Exception as e:
                raise self.BadResponse(
                    f"Failed to parse answer field {i}: {ans_pieces[i]!r}"
                    ) from e
            returnees.append(conv_val)
        return returnees

    def _tell(self, cmd: str):
        mnem, response = self._write_cmd_and_get_response(cmd)
        if response != "OK":
            raise self.BadResponse(response)

    def _get_tick_info(self):
        tick_freq, tick_counter_modulus, hrt_freq, hrt_modulus = self._ask(
            "SCC", (float, int, float, int))
        return tick_freq, tick_counter_modulus, hrt_freq, hrt_modulus

    def _get_ident_info(self):
        board_model, board_id = self._ask("IDN", (str, str))
        return board_model, board_id

    def _get_version_info(self):
        try:
            left, version_desc = self._ask("IVN", (str,str))
        except self.UnsupportedCommand:
            # first gen API didn't have the IVN command
            return (1, 1), "not reported"
        try:
            lleft, lright = left.split(".", 1)
            api_major = int(lleft)
            api_minor = int(lright)
        except ValueError:
            raise self.BadResponse(f"Bad API version string: {left!r}")
        return (api_major, api_minor), version_desc

    def _update_ident_info(self):
        self._board_model, self._board_id = self._get_ident_info()
        self._remote_api_ver, self._fw_commit_hash = self._get_version_info()

    def set_board_id(self, board_id: str) -> str:
        """
        Set the board ID / serial number.

        You must call :meth:`commit_config` afterward for the change to
        persist over a reset / power-cycle.

        The :attr::`board_id` attribute will reflect the change immediately,
        but the board needs to be reset (so that it goes through USB
        enumeration again) before it will be findable under the new ID.

        :param board_id: New board ID
        :returns: The new board ID as reported back by the hardware
        """
        # TODO sanitize and limit length
        self._tell(f"SER={board_id}")
        self._update_ident_info()
        return self.board_id

    def commit_config(self):
        """
        Update the nonvolatile config file from the current config values.

        This is required for any config changes to persist over a reset or
        power cycle.

        Note that current implementations store the nonvolatile config in
        onboard EEPROM which has a finite wear life, so it is not good practice
        for the application to call this routinely.
        """
        self._tell("NVS")

    def revert_config(self):
        """
        Reset current config to the values stored in the nonvolatile config
        file.
        """
        self._tell("NVL")
        self._update_ident_info()

    def load_default_config(self):
        """
        Reset current config to hardcoded firmware defaults.

        Note that this does not automatically update the nonvolatile config
        file. Parameter changes take effect as described under the
        corresponding API methods, i.e. some effects are immediate and some
        happen after a reset.
        """
        self._tell("DEF")
        self._update_ident_info()  # TODO check if actually necessary?

    def reset_to_app(self):
        """
        Disconnect and restart the UXIB hardware.

        The handle to the virtual serial port will be dropped before the
        device disconnects. If you need to continue talking to the board, you
        must discard the current driver instance, wait for the board to be
        enumerated by the host OS again and then open a new driver instance.
        """
        self._tell("RST")
        self.close()

    def reset_to_dfu(self):
        """
        Restart the hardware into DFU mode for updating firmware.

        The current driver instance will be disconnected and the device must
        be restarted by a bootloader command or by a hardware reset before it
        will be accessible again.
        """
        self._tell("DFU")
        self.close()

    def _on_closed_driver_access(self, *args, **kwargs):
        raise self.ConnectionClosed()

    def close(self):
        self._tell = self._on_closed_driver_access
        self._ask = self._on_closed_driver_access
        self._ser_port.close()

    @property
    def board_model(self) -> str:
        """
        The board model name reported by the hardware, e.g. ``"UXIB-DN12"``.
        """
        return self._board_model

    @property
    def board_id(self) -> str:
        """
        The board ID string reported by the hardware, e.g. ``"4E0101"``. This
        is the same as the text of the USB serial number descriptor (see caveat
        below).

        Typically this is treated like a permanent serial number for the board,
        but it can be reassigned arbitrarily if desired.

        This property is updated immediately after setting a new board ID but
        the USB serial number descriptor will not match until the board is
        reenumerated by the OS (after a disconnect or reset).
        """
        return self._board_id

    @property
    def board_fw_ver(self) -> str:
        """
        A string describing the source version for the firmware running on the
        board. Typically this will look something like "v1.2.3", or, more like
        "v0.3.1-0-g042f054+?" for development builds. For firmware builds prior
        to the implementation of this feature, this method returns the fixed
        string "unknown".
        """
        return self._fw_commit_hash

    @property
    def remote_api_ver(self) -> tuple[int, int]:
        """
        A tuple ``(A, B)`` representing which revision of the serial command
        API this board uses, where ``A`` and ``B`` are the major and minor
        revision numbers respectively.
        """
        return self._remote_api_ver

    @property
    def seconds_per_tick(self) -> float:
        """
        Length of the board's general purpose timer tick interval, in seconds
        (typically 1ms).

        Constant for life of session. In current implementations this is fixed
        per board model / firmware revision.
        """
        return self._seconds_per_tick

    @property
    def hrt_resolution_s(self) -> float | None:
        """
        Resolution of the high resolution timer, in seconds (typically 1us).
        ``None`` if HRT not supported.

        Constant for life of session. In current implementations this is fixed
        per board model / firmware revision.

        See note on :attr:`hrt_modulus`.
        """
        return self._hrt_interval_s

    @property
    def tick_counter_modulus(self) -> int:
        """
        The threshold at which the general tick counter rolls over to zero.

        The tick counter follows the usual C89 convention for unsigned integer
        rollover.

        Constant for life of session. In current implementations this is fixed
        per board model / firmware revision.
        """
        return self._tick_counter_mod

    @property
    def hrt_modulus(self) -> int:
        """
        The threshold at which the high resolution timer rolls over to zero.

        The HRT value follows the usual C89 convention for unsigned integer
        rollover.

        Note that the HRT may or may not have a relationship with the general
        tick counter, and the application should not assume any.

        Constant for life of session. In current implementations this is fixed
        per board model / firmware revision.
        """
        return self._hrt_counter_mod

    @property
    def features(self) -> set[str]:
        return set(self._feature_names)

    @property
    def serial_portname(self) -> str:
        return self._portname

    @property
    def usb_location(self) -> str:
        return self._usb_loc

    @property
    def usb_vidpid(self) -> tuple[int, int] | None:
        return self._usb_vidpid


class UxibxxIoBoard(UxibxxIoBoardBase):
    USB_VIDPIDS = set(USB_VIDPID_FOR_MODEL.values())



from . import boards
_board_modules = [boards.dn12, boards.shf4, boards.ljpm]
_driver_info_for_vidpid = {
    vidpid: (mod.MODEL_NAME, mod._BoardModelDriverCls)
    for mod in _board_modules
    for vidpid in mod._BoardModelDriverCls.USB_VIDPIDS
    }
