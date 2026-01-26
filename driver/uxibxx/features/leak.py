from collections.abc import Iterable

from ..types import LeakDetectorResult, LeakDetectorRawReading, _NoData
from .._common import autoint


LEAK_VALID_CHANNELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# TODO should we make valid ranges for flow and leak not overlap?


class LeakDetector:
    def __init__(self, *args, **kwargs):
        self._leak_update_channel_lists()
        self._add_feature_name("leak")
        super().__init__()

    def _leak_update_channel_lists(self):
        # TODO come up with a nice way of handling variable length comma separated answers in the main parser
        self._leak_channel_names = "".join(self._ask("LSN", (str,), 1)[0].split(","))

    def enable_leak_detector(
            self,
            channels: Iterable[str] | None,
            on: bool = True
            ) -> list[str]:
        """
        Enable or disable the leak detector function on the specified channels.
        If said channels are already in the requested state, this has no
        effect.

        Depending on the implementation, the I/O pins associated with a
        disabled leak detector channel may be clamped to GND or set to
        high-impedance. Future implementations may support using those pins for
        other functions (e.g. digital I/O).

        Current implementations have the leak detector channels inactive on
        powerup, so the application must explicitly enable them. In the future
        there will be a nonvolatile config parameter to set leak detector
        channels to be enabled automatically on powerup.

        :param channels: Identifier(s) of the channel(s) to operate on. If 
            ``None``, apply to all channels.
        :param on: Whether to enable (``True``) or disable (``False``) the
            leak detector function.
        :returns: List of affected channels
        """
        if channels is None:
            channels = self.leak_detector_channels
        else:
            channels = list(channels)
        for ch_name in channels:
            self._tell(f"LSE:{ch_name[:1]}={int(bool(on))}")
        return channels

    def get_leak_status(self, channel: str) -> LeakDetectorResult:
        """
        Get the current detection status of the specified leak detector
        channel.

        :param channel: Identifier of the channel to ask about
        :returns: A :class:`LeakDetectorResult` object.
        """
        try:
            status_int, ts_tick = self._ask(
                f"LSS:{channel}", (autoint, autoint))
        except _NoData:
            return LeakDetectorResult.from_int(
                LeakDetectorStatus.LEAK_NODATA, ts_tick=None, data_valid=False)
        try:
            return LeakDetectorResult.from_int(
                status_int, ts_tick=ts_tick, data_valid=True)
        except ValueError as e:
            raise self.BadResponse() from e # TODO message?

    def get_leak_raw(self, channel: str) -> LeakDetectorRawReading | None:
        """
        Get the current detection status of the specified leak detector
        channel.

        :param channel: Identifier of the channel to ask about
        :returns: A :class:`LeakDetectorResult` object.
        """
        try:
            ab, ba, ts_tick = self._ask(
                f"LSR:{channel}", (autoint, autoint, autoint))
        except _NoData:
            return None
        return LeakDetectorRawReading(ab=ab, ba=ba, ts_tick=ts_tick)

    def set_leak_detect_threshold(self, channel: str, val: int) -> int:
        """
        Sets the detection threshold for channel ``channel``. The channel will
        be in "liquid detected" status any time the ADC count is below this
        value.

        :param channel: Identifier of the channel set the threshold for
        :param val: New leak detect threshold value
        :returns: New leak detect threshold value as reported back by the
            hardware
        """
        self._tell(f"LSL:{channel[:1]}={val:05d}")
        return self.get_leak_detect_threshold(channel)

    def get_leak_detect_threshold(self, channel: str) -> int:
        """
        Get the current detection threshold for the specified channel. See
        :meth:`set_leak_detect_threshold` for more explanation.

        :param channel: Identifier of the channel to ask about
        :returns: Leak detect threshold value for the specified channel
        """
        return self._ask(f"LSL:{channel}", (int,))[0]

    def get_leak_fault_thresholds(self, channel: str) -> tuple[int, int]:
        """
        Get the current open circuit and short circuit thresholds for the
        specified channel.

        See :meth:`set_leak_fault_thresholds` for more explanation of the
        fault thresholds.

        :param channel: Identifier of the channel to ask about
        :returns: A tuple ``(short, open)`` where ``short`` and ``open`` are
            the threshold values for the shorted and open-circuit conditions
            as described above.
        """
        open_thresh, short_thresh = self._ask(
            f"LSF:{channel[:1]}", (int, int))
        return open_thresh, short_thresh

    def set_leak_fault_thresholds(
            self,
            channel: str,
            short_thresh: int | None = None, 
            open_thresh: int | None = None
            ) -> tuple[int, int]:
        """
        Set the open circuit and short circuit thresholds for the specified
        channel.

        The channel will be in "short circuit" status when either the forward
        or reverse sensing ADC count is equal to or less than ``short_thresh``.
        It will be in "open circuit" status (i.e. unplugged or a wire is
        broken) when either the forward or reverse sensing ADC count is
        greater than or equal to ``open_thresh``.
        
        :param channel: Identifier of the channel to set new thresholds on
        :returns: A tuple ``(short, open)`` with the new values as reported
            back by the hardware.
        """
        if any(x is None for x in (short_thresh, open_thresh)):
            curr_short, curr_open = self.get_leak_fault_thresholds(channel)
        short_thresh = short_thresh if short_thresh is not None else curr_short
        open_thresh = open_thresh if open_thresh is not None else curr_open
        self._tell(f"LSF:{channel}={short_thresh:05d},{open_thresh:05d}")
        return self.get_leak_fault_thresholds(channel)

    def get_leak_open_threshold(self, channel: str) -> int:
        """
        Get the open circuit threshold for the specified channel.

        This is a convenience method wrapping
        :meth:`get_leak_fault_thresholds`. Refer to that method's documentation
        for more info.

        :param channel: Identifier of the channel to ask about
        :returns: Threshold value reported by the hardware
        """
        short, open_ = self.get_leak_fault_thresholds(channel)
        return open_

    def get_leak_short_threshold(self, channel: str) -> int:
        """
        Get the open circuit threshold for the specified channel. See
        :meth:`get_leak_fault_thresholds` for more info.

        This is a convenience method wrapping
        :meth:`get_leak_fault_thresholds`. Refer to that method's documentation
        for more info.

        :param channel: Identifier of the channel to ask about
        :returns: Threshold value reported by the hardware
        """
        short, open_ = self.get_leak_fault_thresholds(channel)
        return short

    def set_leak_open_threshold(self, channel: str, thresh: int) -> int:
        """
        Set the open circuit threshold for the specified channel.

        This is a convenience method wrapping
        :meth:`set_leak_fault_thresholds`. Refer to that method's documentation
        for more info.

        :param channel: Identifier of the channel to set the threshold for
        :returns: New threshold as reported back by the hardware
        """
        short, open_ = self.set_leak_fault_thresholds(
            channel, open_thresh=thresh)
        return open_

    def set_leak_short_threshold(self, channel: str, thresh: int) -> int:
        """
        Set the short circuit threshold for the specified channel.

        This is a convenience method wrapping
        :meth:`set_leak_fault_thresholds`. Refer to that method's documentation
        for more info.

        :param channel: Identifier of the channel to set the threshold for
        :returns: New threshold as reported back by the hardware
        """
        short, open_ = self.set_leak_fault_thresholds(
            channel, short_thresh=thresh)
        return short

    def get_leak_sample_interval(self, channel: str) -> float:
        """
        Get the nominal interval between measurement cycles for this leak
        sensor channel. Note that this may be implemented as a minimum delay
        time, in which case the average interval between measurements will be
        slightly longer than the nominal value.

        :param channel: Identifier of the channel to retrieve the value for
        :returns: Nominal sample interval in seconds

        """
        itvl_ticks = self._ask(f"LST:{channel[:1]}", (int,))[0]
        return itvl_ticks * self.seconds_per_tick

    @property
    def leak_detector_channels(self) -> list[str]:
        """
        List of all leak detector channel names. Channel names consist of a
        single alphanumeric character and should match the label on the
        corresponding connector. They are not necessarily consecutive
        letters/numbers.
        """
        return list(self._leak_channel_names)
