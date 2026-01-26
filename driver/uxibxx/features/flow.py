from collections.abc import Iterable

from ..types import (
    _NoData, FlowSensorInfo, FlowRateHistoryResult, FlowRateHistoryRow,
    FlowSample, FlowSampleRaw, FlowSampleFlags, VolMeasurementResult,
    VolMeasurementResults, VolMeasurementNotStarted
    )
from .._common import autoint


FLOW_VALID_CHANNELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class FlowMeasurement:
    def __init__(self, *args, **kwargs):
        self._flow_vol_in_progress = {}
        self._flow_update_channel_lists()
        self._flow_update_sensor_info()
        self._add_feature_name("flow")
        super().__init__()

    def _flow_update_channel_lists(self):
        # TODO come up with a good way to deal with the comma separated list situation in the parser
        self._flow_channel_names = "".join(
            self._ask("TFN", (str,), 1)[0].split(","))
        self._flow_channels_available = "".join(
            self._ask("TFA", (str,), 1)[0].split(","))
        self._flow_channels_failed = "".join(
            self._ask("TFF", (str,), 1)[0].split(","))

    def _flow_update_sensor_info(self):
        left, right = self._ask("TFM", (int, int))
        self._flow_totalizer_mod = 2 ** left
        self._flow_supersample_interval_s = right * self.seconds_per_tick
        self._flow_sample_interval = {}
        self._flow_sensor_info = {}
        self._flow_sensor_range = {}
        for ch_name in self.flow_sensors_available:
            self._flow_sample_interval[ch_name] = self._ask(
                f"TFS:{ch_name}", (float,))[0]
            sensor_family_name, sensor_prod_id, sensor_serial_no = self._ask(
                f"TFI:{ch_name}", (str, str, str))
            self._flow_sensor_info[ch_name] = FlowSensorInfo(
                sensor_family_name, sensor_prod_id, sensor_serial_no)
            self._flow_sensor_range[ch_name] = (-40., 40.) # FIXME TODO

    def enable_flow_measurement(
            self, channels: Iterable[str] | None, on: bool = True
            ) -> list[str]:
        """
        Start up or shut down continuous measurement from the flow sensor(s).
        If we are already in the requested state, this has no effect.

        After stopping measurements, the sensor may be transitioned to some
        kind of intermediate standby state, depending on the implementation.

        :param channels: Identifier(s) of the channel(s) to operate on. If 
            ``None``, apply to all channels.
        :param on: Whether to start (``True``) or stop (``False``) the
            measurement process.
        :returns: List of affected channels
        """
        if channels is None:
            channels = self.flow_sensors_available
        else:
            channels = list(channels)
        for ch_name in channels:
            self._tell(f"TFE:{ch_name[:1]}={int(bool(on))}")
        return channels

    def get_running_flow_channels(self) -> list[str]:
        return [
            ch_name for ch_name in self.flow_sensors_available
            if self._ask(f"TFE:{ch_name[:1]}", (int,))[0]
            ]

    def start_vol_total(self, channels: Iterable[str]):
        """
        Mark the start point for a total volume measurement. If a measurement
        was already running it will be reset.

        If flow measurement is not currently running on this channel, it will
        be started and the reference point will be set at the point where
        measurement startup is complete and data is presumed valid. Otherwise
        the reference point is set at the time of the next sample from the
        sensor. It may be preferable to explicitly start flow measurement
        ahead of time to ensure data is immediately available when starting
        a new volume measurement.

        Note that totalization runs continously whenever flow measurement is
        active. Internally, volume totals are calculated from the change in 
        the accumulator value between two points in time. If desired, you
        can also retrieve the raw accumulator value using
        :meth:`get_totalizer_count`.

        :param channels: Identifier(s) of the channel(s) to operate on
        """
        channels = "".join(s[:1] for s in channels)
        self.enable_flow_measurement(channels)
        self._tell(f"TFT:{channels}")
        self._flow_vol_in_progress.update({
            ch_name: True for ch_name in channels})

    def get_vol_channel_running(self, ch_name: str) -> bool:
        """
        FIXME
        """
        return bool(self._ask(f"TFY:{ch_name[0]}", (int,))[0])

    def get_vol_channels_running(self) -> list[str]:
        """
        FIXME
        """
        return [
            ch_name
            for ch_name in self.flow_sensors_available
            if self.get_vol_channel_running(ch_name)
            ]

    def get_vol_total(self, channels: Iterable[str], stop: bool = True
            ) -> VolMeasurementResults:
        """
        Get the total measured volume of fluid that passed through the sensor
        since calling :meth:`start_vol_total`.

        Note that if the sensor is capable of bidirectional measurements and
        produces signed raw readings, flow in the reverse direction will cancel
        out flow in the forward direction, e.g. if there is 10mL of forward
        flow followed by 8mL of reverse flow, the final total will be 2mL.

        If `stop` is false, the reference point is kept and you can keep calling
        :meth:`get_vol_total` to get an updated total. Otherwise it will be
        cleared and :meth:`start_vol_total` must be called to start a new
        measurement before calling :meth:`get_vol_total` again.
        Flow measurement will continue running regardless, until turned off
        using :meth:`enable_flow_measurement`.

        :param channels: Identifier(s) of the channel(s) to operate on
        :param stop: Whether or not to automatically end the volume
            measurement (equivalent to calling :meth:`stop_vol_total`)
        """
        channels = "".join(s[:1] for s in channels)
        for ch_name in channels:
            if not (
                    self._flow_vol_in_progress.get(ch_name, False)
                    or self.get_vol_channel_running(ch_name)
                    ):
                raise VolMeasurementNotStarted(
                    f"Volume measurement not running on channel {ch_name!r}"
                    )
        if channels:
            self._tell("TFU:" + channels)  # capture total volume(s)
        results = []
        for ch_name in channels:
            first_tick, last_tick, vol = self._ask(
                f"TFV:{ch_name}", (autoint, autoint, float))
            elapsed_s = (last_tick - first_tick) * self.seconds_per_tick
            results.append((
                ch_name,
                VolMeasurementResult(
                    total_ml=vol,
                    first_tick=first_tick,
                    last_tick=last_tick,
                    elapsed_s=elapsed_s
                    )
                ))
        if stop and channels:
            self.stop_vol_total(channels)
        return VolMeasurementResults(results)

    def stop_vol_total(self, channels: Iterable[str]):
        """
        Clear the reference point for total volume measurement. This does not
        stop flow measurement readout from the sensor.

        This mainly exists as an option to guard against false readings due to
        faulty application logic. There is no performance benefit to "stopping"
        the volume measurement.

        :param channels: Identifier(s) of the channel(s) to operate on
        """
        channels = "".join(s[:1] for s in channels)
        for ch_name in channels:
            self._tell(f"TFX:{ch_name}")
            self._flow_vol_in_progress[ch_name] = False

    def get_flow_rate(self, channel: str) -> float | None:
        """
        Get the calculated average flow rate value for the most recent flow
        measurement interval, for the specified ``channel``, in milliliters
        per minute. If you are trying to capture consecutive values for
        plotting/analysis or want timestamped data, you should use
        :meth:`get_flow_rate_history`.

        Note that this will not automatically turn on flow measurement, and
        could return stale data if flow measurement has been stopped.

        :param channel: Identifier of the channel to operate on
        :returns: Most recent average flow rate in mL/minute, or ``None`` if 
            there is no data.
        """
        try:
            flow_rate = self._ask(f"TFC:{channel}", (float,))[0]
        except _NoData:
            return None
        return flow_rate

    def _get_flow_rate_history_row(self, channel: str) -> FlowRateHistoryRow:
        ts_end, flow_val = self._ask(f"TFH:{channel}", (int, float))
        return FlowRateHistoryRow(
            ml_per_min = flow_val,
            start_tick = ts_end - self.flow_ss_interval,
            end_tick = ts_end,
            elapsed_s = self.flow_ss_interval
            )

    def get_flow_rate_history(self, channel: str) -> FlowRateHistoryResult:
        """
        Fetch all flow rate supersamples since the last call to
        :meth:`get_flow_rate_history`.

        See :class:`FlowRateHistoryResult` for more details on the output data
        structure.

        Incoming samples are averaged over consecutive, non-overlapping time
        windows of fixed width and the resulting supersamples are timestamped
        and held in a buffer until fetched by the host. If the buffer fills up
        between fetches, the oldest values will start to be dropped and this
        will be reflected in the ``n_dropped_before`` (number dropped between
        calls to :meth:`get_flow_rate_history`) and ``n_dropped_between``
        (number dropped while trying to offload them) attributes of the
        :class:`FlowRateHistoryResult`.

        Data is handed over first-in, first-out. You can always peek at the
        most recent value using :meth:`get_flow_rate`, which does not affect
        the queue.

        :param channel: Identifier of the channel to operate on
        :returns: A :class:`FlowRateHistoryResult` with the most recent data
        """
        n_dropped_before = 0
        n_dropped_between = 0
        rows = []
        first = True
        while True:
            try:
                row, n_dropped = self._get_flow_rate_history_row()
            except _NoData:
                break
            rows.append(row)
            if first:
                n_dropped_before = n_dropped
                first = False
            else:
                n_dropped_between += n_dropped
        return FlowRateHistoryResult(
            rows=rows,
            n_dropped_before=n_dropped_before,
            n_dropped_between=n_dropped_between
            )

    def get_flow_totalizer_count(self, channel: str) -> int:
        """
        For special use or diagnostic purposes.

        Returns the current accumulator value from the totalizer.

        The relationship of this value to physical units depends on the sensor.

        :param channel: Identifier of the channel to operate on
        """
        return self._ask(f"TFD:{channel}", (int,))[0]

    def get_last_flow_sample_raw(self, channel: str) -> FlowSampleRaw:
        """
        For special use or diagnostic purposes.

        Returns the most recently recorded raw sample value from the sensor,
        or ``None`` if there isn't one.

        The relationship of this value to physical units depends on the sensor.

        See commentary on :meth:`get_last_flow_sample`.

        :param channel: Identifier of the channel to operate on
        :returns: A :class:`FlowRawSample` instance representing the most 
            recent sample captured on this channel, or ``None`` if no samples 
            have been read from the sensor yet
        """
        try:
            flow_value, temp_value, ts_tick, flags_int = self._ask(
                f"TFR:{channel}", (int, int, autoint, int))
        except _NoData:
            return None
        try:
            flags = FlowSampleFlags(flags_int)
        except ValueError as e:
            raise self.BadResponse() from e
        return FlowSampleRaw(
            ts_tick=ts_tick,
            flow_value=flow_value,
            temp_value=temp_value,
            flags=flags
            )

    def get_last_flow_sample(self, channel: str) -> FlowSample:
        """
        Same idea as :meth:`get_last_flow_sample_raw` but values are 
        translated to physical units.

        Note, you probably don't want to use this for normal measurements,
        unless you need a measurement over the smallest feasible time window.
        You can't request samples as quickly as the board reads them out from
        the sensors, so in a continuous measurement scenario you will be
        throwing away a lot of information in between measurement points.

        For most use cases you probably want to use
        :meth:`get_flow_rate_history`, or at least :meth:`get_flow_rate`.


        :param channel: Identifier of the channel to operate on
        :returns: A :class:`FlowRawSample` instance representing the most 
            recent sample captured on this channel, or ``None`` if no samples 
            have been read from the sensor yet
        """
        raw = self.get_last_flow_sample_raw(channel)
        return FlowSample(
            ts_s=raw.ts_tick * self.seconds_per_tick,
            # FIXME get conversion factors from the board
            ml_per_min=raw.flow_value * 1./500., # TODO,
            temp_degc=raw.temp_value * 1./200., # TODO,
            flags=raw.flags
            )

    @property
    def flow_sensor_channels(self) -> list[str]:
        """
        List of all valid flow sensor channel names. Channel names consist of 
        a single alphanumeric character and should match the label on the
        corresponding sensor connector. They are not necessarily consecutive
        letters/numbers.

        Note this does not indicate whether any sensors are actually present
        (see :attr:`flow_sensors_available`).
        """
        return list(self._flow_channel_names)

    @property
    def flow_sensors_available(self) -> list[str]:
        """
        List of flow sensor channel names for which sensors are connected and
        were successfully initialized at startup.

        Channels which were defined in the board configuration but for which
        no sensor appeared to be physically connected at startup are simply
        left off this list. Channels deactivated due to communications or
        other failures can be listed using :meth:`flow_sensors_failed`.
        """
        return list(self._flow_channels_available)

    # TODO (FW & driver): Report type of sensor (some kind of symbolic name),
    # rated flow rate range, any ID values...

    @property
    def flow_sensors_failed(self) -> list[str]:
        """
        List of flow sensor channel names for which the sensor appeared to be
        present at startup but for which initialization was unsucessful or a
        problem during operation caused the channel to be marked as failed.
        """
        return list(self._flow_channels_failed)

    @property
    def flow_totalizer_modulus(self) -> int:
        """
        The value at which the accumulator rolls over to zero. The accumulator
        follows the usual C89 convention for unsigned integer rollover.

        You don't really need to think about this unless you are doing your own
        client-side volume tracking or something with the raw totalizer counts.
        """
        return self._flow_totalizer_mod
    
    @property
    def flow_sample_interval(self) -> dict[str, float]:
        """
        The nominal time interval between raw samples from each sensor, in
        seconds.

        For the Sensiron SL3x sensors this is fixed at 0.5ms. Note however
        that individual sensors do not run at precisely the same rate.
        """
        return self._flow_sample_interval.copy()

    @property
    def flow_sensor_info(self) -> dict[str, FlowSensorInfo]:
        return self._flow_sensor_info.copy()

    @property
    def flow_sensor_range(self) -> dict[str, tuple[float, float]]:
        return self._flow_sensor_range.copy()

    @property
    def flow_ss_interval(self) -> float:
        """
        The length of the time interval represented by each supersample as
        returned from :meth:`get_flow_rate_history`, in seconds.

        In the current firmware implementation this is fixed at 100ms. In the
        future it may be a configurable parameter.
        """
        return self._flow_supersample_interval_s
