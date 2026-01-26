import logging

from .._common import hexint



logger = logging.getLogger(__name__)



class ISquaredC:
    def __init__(self, *args, **kwargs):
        self._i2c_channel_names = self._i2c_get_channel_list()
        self._add_feature_name("i2c")
        super().__init__()

    def _i2c_get_channel_list(self):
        try:
            return list(self._ask("IIL", (str,)))
        except self.UnsupportedCommand:
            return []

    def i2c_write_reg(
            self, channel: str, chip_addr: int, reg_addr: int, data: bytes):
        """
        Do a multi-byte register write transaction with a single byte register
        address.

        :param channel: I2C channel name (see :prop:`i2c_channels`)
        :param chip_addr: I2C address of the device to write to
        :param reg_addr: single byte register address to write to
        :param data: ``bytes`` object or a sequence of integers representing
            bytes to be written.
        """
        # TODO check payload against max length reported by board
        n_bytes = len(data)
        for i, x in enumerate(data):
            self._tell(f"IIB:{i:d}={x:02X}")
        self._tell(f"IIW:{channel},{chip_addr:02X},{reg_addr:02X}={n_bytes:d}")

    def i2c_write_raw(self, channel: str, chip_addr: int, data: bytes):
        """
        Do an unstructured write to the specified device address.

        :param channel: I2C channel name (see :prop:`i2c_channels`)
        :param chip_addr: I2C address  of the device to write to
        :param data: ``bytes`` object or a sequence of integers representing
            bytes to be written.
        """
        # TODO check payload against max length reported by board
        n_bytes = len(data)
        for i, x in enumerate(data):
            self._tell(f"IIB:{i:d}={x:02X}")
        self._tell(f"IIY:{channel},{chip_addr:02X}={n_bytes:d}")

    def i2c_read_reg(
            self, channel: str, chip_addr: int, reg_addr: int, n_bytes: int
            ) -> bytes:
        """
        Do a multi-byte register read transaction with a single byte register
        address.

        :param channel: I2C channel name (see :prop:`i2c_channels`)
        :param chip_addr: I2C address  of the device to read from
        :param reg_addr: single byte register address to start reading at
        :param n_bytes: number of bytes to attempt to read
        :returns: a `bytes()` object containing the received data.
        """
        logger.debug(f"i2c_read_reg({channel!r}, {chip_addr:02X}, {reg_addr:02X}, {n_bytes:d})")
        self._tell(f"IIR:{channel},{chip_addr:02X},{reg_addr:02X}={n_bytes:d}")
        n_bytes_read = self._ask(f"IIL", (int,))[0]
        return bytes(
            self._ask(f"IIB:{i:d}", (hexint,))[0] for i in range(n_bytes_read)
            )

    def i2c_read_raw(
            self, channel: str, chip_addr: int, n_bytes: int
            ) -> bytes:
        """
        Do an unstructured read from the specified device address.

        :param channel: I2C channel name (see :prop:`i2c_channels`)
        :param chip_addr: I2C address  of the device to read from
        :param n_bytes: number of bytes to attempt to read
        :returns: a `bytes()` object containing the received data.
        """
        self._tell(f"IIX:{channel},{chip_addr:02X}={n_bytes:d}")
        n_bytes_read = self._ask(f"IIL", (int,))[0]
        return bytes(
            self._ask(f"IIB:{i:d}", (hexint,))[0] for i in range(n_bytes_read)
            )

    @property
    def i2c_channels(self) -> list[str]:
        """
        List of channel names corresponding to I2C interfaces on the device.

        Channel names consist of a single uppercase latin alphabetic character
        and are assigned to match the markings on the physical ports on the
        device. Where one interface is wired to multiple ports, the channel
        is named for the first physical port label (in lexical order) in the
        group.

        All that said, the preceding paragraph is moot for the current
        hardware generation because all current devices have at most a single
        I2C channel, "A".
        """
        return list(self._i2c_channel_names)
