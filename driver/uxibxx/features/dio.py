from .. import types



class _DigitalIoBase:
    InvalidTerminalNo = types.InvalidTerminalNo
    IoDirection = types.IoDirection
    _direction_codes = [
        (0, IoDirection.INPUT),
        (1, IoDirection.OUTPUT),
        ]


class DigitalIo(_DigitalIoBase):
    # TODO make these mixins a little less frustrating for the poor linter

    def __init__(self, *args, **kwargs):
        term_nos = self._get_term_nos()
        self._terminal_capabilities = {
            term_no: self._ask(f"TCP:{term_no}", (str,))[0] for term_no in term_nos
            }
        self._add_feature_name("dio")
        super().__init__()

    def _get_term_nos(self):
        response = self._ask("TLS", (str,), 1)[0].split(",")
        # TODO can we have the parser take care of this in a nonugly way?
        try:
            term_nos = [int(x) for x in response]
        except ValueError:
            raise self.BadResponse(response)
        return term_nos

    def _check_output_ok(self, n: int):
        if n not in self._terminal_capabilities:
            raise self.InvalidTerminalNo(n)
        if n not in self.output_nos:
            raise self.Unsupported(
                f"Terminal {n} does not have output capability")

    def _check_output_pulse_ok(self, n: int):
        self._check_output_ok(n)
        if self.remote_api_ver < (3, 1):
            raise self.Unsupported(
                f"Firmware does not support the output pulse command or it is "
                f"not allowed for terminal {n}"
                )
            # Note: Currently there aren't any actual implementations that
            # restrict the output pulse function per-terminal

    def _check_input_ok(self, n: int):
        if n not in self._terminal_capabilities:
            raise self.InvalidTerminalNo(n)
        if n not in self.input_nos:
            raise self.Unsupported(
                f"Terminal {n} does not have input capability")

    def _check_dirchange_ok(self, n: int):
        if n not in self._terminal_capabilities:
            raise self.InvalidTerminalNo(n)
        if n not in self.input_nos or n not in self.output_nos:
            raise self.Unsupported(
                f"Terminal {n} does not support changing I/O direction")

    def get_input(self, n: int) -> bool:
        """
        Reads out the current input state of the specified terminal.

        Inputs can be *active* or *inactive*; what this means electrically
        is hardware-dependent, but the convention for logic-level inputs
        is that *active* corresponds high logic level.

        :param n: Terminal number
        :returns: `True` if the input is active, otherwise `False`.
        :raises InvalidTerminalNo: if the specified terminal number is invalid
        :raises Unsupported: if the specified terminal does not have input
            capability
        :raises ResponseTimeout,RemoteError,BadResponse: see class descriptions
        """
        if n not in self._terminal_capabilities:
            raise self.InvalidTerminalNo(n)
        if n not in self.input_nos:
            raise self.Unsupported(
                f"Terminal {n} does not have input capability")
        answer = self._ask(f"INP:{n}", (int,))[0]
        return bool(answer)

    def get_output(self, n: int) -> bool:
        """
        Reads out the current output state of the specified terminal.

        :param n: Terminal number
        :returns: `True` if the output is active, otherwise `False`.
            See note on :meth:`set_output`.
        :raises InvalidTerminalNo: if the specified terminal number is invalid
        :raises Unsupported: if the specified terminal does not have output
            capability
        :raises ResponseTimeout,RemoteError,BadResponse: see class descriptions
        """
        self._check_output_ok(n)
        answer = self._ask(f"OUT:{n}", (int,))[0]
        return bool(answer)

    def set_output_initial(self, n: int, on: int | bool):
        """
        NOT YET IMPLEMENTED.

        Sets the initial / failsafe value for the specified output. This is
        the value that will be applied when the board is first powered on,
        after a firmware reset, or when various failsafe mechanisms are
        triggered.

        Note that in the absence of a valid nonvolatile config file the
        initial states will be set according to hardcoded firmware defaults;
        in current implementations the default is for all outputs to be set to
        the "inactive" state. Be mindful of this in applications where there
        is a potential for loss or damage.

        Note that calling this method does not automatically update the
        nonvolatile config file.

        Refer to :meth:`set_output` for explanation of output states.

        :param n: Terminal number
        :param on: New initial output state.
        :raises InvalidTerminalNo: if the specified terminal number is invalid
        :raises Unsupported: if the specified terminal does not have output
            capability
        :raises ResponseTimeout,RemoteError,BadResponse: see class descriptions
        """
        raise NotImplementedError()

    def set_output(self, n: int, on: int | bool):
        """
        Sets the output state of the specified terminal.

        Outputs can be *active* or *inactive*; what this means electrically
        is hardware-dependent; however, the convention for logic-level outputs
        is that *active* corresponds to logic high, and for power outputs
        *active* means the load is energized.

        :param n: Terminal number
        :param on: New output state. If `False` or zero the output becomes
            inactive. If `True` or nonzero the output becomes active.
        :raises InvalidTerminalNo: if the specified terminal number is invalid
        :raises Unsupported: if the specified terminal does not have output
            capability
        :raises ResponseTimeout,RemoteError,BadResponse: see class descriptions
        """
        self._check_output_ok(n)
        self._tell(f"OUT:{n}={int(bool(on))}")

    def pulse_output(self, n: int, on: int | bool, interval: float,
                     wait: bool = False):
        """
        Generates an output pulse: the specified terminal takes the specified
        logic state for a defined time interval, then switches to the opposite
        state after a specified time interval.

        Any subsequent command or event that touches the output state before
        the time interval elapses (even setting it to the same state) will
        take effect immediately and cancel the pulse sequence.

        The output will always take the opposite of the specified state
        regardless of the state of the output before the command. You could
        use this to change an output after a time delay, for example.

        See note on :meth:`set_output` regarding the convention for output
        states.

        This method returns immediately unless ``wait`` is ``True``, in which
        case it will block until the pulse sequence finishes or is cancelled.

        :param n: Terminal number
        :param on: Temporary output state. If `False` or zero the output
            becomes inactive. If `True` or nonzero the output becomes active.
            The final output state will be the opposite.
        :param interval: Delay interval in seconds. This will be rounded up to
            the next multiple of :attr:`seconds_per_tick`.
        :param wait: Whether to block while the pulse sequence is in progress.
        :raises InvalidTerminalNo: if the specified terminal number is invalid
        :raises Unsupported: if the specified terminal does not have output
            capability or the firmware does not support this function
        :raises ResponseTimeout,RemoteError,BadResponse: see class descriptions
        """
        self._check_output_pulse_ok(n)
        if self.hrt_resolution_s is not None:
            tb_freq = 1. / self.hrt_resolution_s
        else:
            tb_freq = 1. / self.seconds_per_tick
        self._tell(f"OUP:{n}={int(bool(on))},{round(interval * tb_freq)}")


    def get_direction(self, n: int) -> 'types.IoDirection':
        """
        Reads out the current I/O direction of the specified terminal

        :param n: Terminal number
        :returns: The current I/O direction of the specified terminal
        :raises InvalidTerminalNo: if the specified terminal number is invalid
        :raises ResponseTimeout,RemoteError,BadResponse: see class descriptions
        """
        if n not in self._terminal_capabilities:
            raise self.InvalidTerminalNo(n)
        response = self._ask(f"DIR:{n}", (int,))[0]
        try:
            dir_int = int(response)
            return dict(self._direction_codes)[dir_int]
        except KeyError as e:
            raise self.BadResponse() from e

    def set_direction(
            self, n: int,
            direction: types._IoDirectionOrLiteral
            ):
        """
        Sets the I/O direction of the specified terminal.
        See :class:`IoDirection` for further explanation.

        :param n: Terminal number
        :param direction: I/O direction to set the terminal to, either a
            :class:`IoDirection` member or the corresponding string literal.
        :raises InvalidTerminalNo: if the specified terminal number is invalid
        :raises Unsupported: if the specified terminal does not support the
            requested mode.
        :raises ResponseTimeout,RemoteError,BadResponse: see class descriptions
        """
        self._check_dirchange_ok(n)
        direction = self.IoDirection(direction)
        dir_code = dict((y, x) for (x, y) in self._direction_codes)[direction]
        self._tell(f"DIR:{n}={dir_code}")

    def set_direction_initial(
            self, n: int,
            direction: types._IoDirectionOrLiteral
            ):
        """
        NOT YET IMPLEMENTED.

        Sets the initial I/O direction of the specified terminal.

        This operates similarly to :meth:`set_output_initial`.

        Refer to :meth:`set_direction` for explanation of I/O direction.

        :param n: Terminal number
        :param direction: I/O direction to set the terminal to, either a
            :class:`IoDirection` member or the corresponding string literal.
        :raises InvalidTerminalNo: if the specified terminal number is invalid
        :raises Unsupported: if the specified terminal does not support the
            requested mode.
        :raises ResponseTimeout,RemoteError,BadResponse: see class descriptions
        """
        raise NotImplementedError()

    @property
    def terminal_nos(self) -> list[int]:
        """
        A list of available terminal numbers under this board's current
        configuration. Valid terminal numbers range from 1 to 255. Terminal
        numbers are arbitrary and not necessarily consecutive.

        Any configuration changes that affect terminal number assignments
        shall take effect after a firmware reset, therefore this value can be
        treated as constant for the life of a session.
        """
        return list(self._terminal_capabilities.keys())

    @property
    def input_nos(self) -> list[int]:
        """
        A list of the terminal numbers for terminals that are inputs or support
        being set to input mode.

        Constant for the life of a session (see :attr:`terminal_nos`).
        """
        return [
            term_no for (term_no, caps) in self._terminal_capabilities.items()
            if "I" in caps
            ]

    @property
    def output_nos(self) -> list[int]:
        """
        A list of the terminal numbers for terminals that are outputs or
        support being set to output mode.

        Constant for the life of a session (see :attr:`terminal_nos`).
        """
        return [
            term_no for (term_no, caps) in self._terminal_capabilities.items()
            if "O" in caps
            ]
