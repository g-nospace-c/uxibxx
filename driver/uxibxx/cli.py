import argparse
from collections.abc import Iterable
import logging
import sys
import time

import serial

from uxibxx import UxibxxIoBoard
from uxibxx.features.flow import FLOW_VALID_CHANNELS
from uxibxx.features.leak import LEAK_VALID_CHANNELS



def parse_flow_channel_list(raw: str) -> list[str] | None:
    channels = [x for x in raw if x not in "\r\n\t ,;"]
    if "".join(channels) == "all" or not channels:
        return None
    for ch_name in channels:
        if ch_name not in FLOW_VALID_CHANNELS:
            raise ValueError(
                f"Illegal character in flow sensor channel list: {ch_name!r}")
    return channels


def parse_leak_channel_list(raw: str) -> list[str] | None:
    # TODO deduplicate?
    channels = [x for x in raw if x not in "\r\n\t ,;"]
    if "".join(channels) == "all" or not channels:
        return None
    for ch_name in channels:
        if ch_name not in LEAK_VALID_CHANNELS:
            raise ValueError(
                f"Illegal character in leak sensor channel list: {ch_name!r}")
    return channels


def parse_cli_args(argv_rh: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        epilog="If a specific board is not selected (-p, -d), the "
               "\"first\" device, if any, will be used."
        )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Forward DEBUG-level log messages to the terminal"
        )

    info_group = parser.add_argument_group(title="Enumeration")
    info_group.add_argument(
        "-l", "--list",
        action="store_true",
        help="Output a list of connected devices"
        )

    devselect_group = parser.add_argument_group(title="Device selection")
    devselect_mutex = devselect_group.add_mutually_exclusive_group()
    devselect_mutex.add_argument(
        "-p", "--port",
        metavar="PORTNAME",
        help="Select board on virtual serial port identified by PORTNAME "
             "(naming is platform dependent: COM3, /dev/ttyACM0, etc.)"
        )
    devselect_mutex.add_argument(
        "-d", "--bid",
        metavar="BOARD_ID",
        help="Select board according to board ID string BOARD_ID"
        )

    action_subs = parser.add_subparsers(dest="action_group", title="Actions")

    info_sub = action_subs.add_parser("info", help="Get board info")

    util_sub = action_subs.add_parser("util", help="Maintenance stuff")
    util_sub_subs = util_sub.add_subparsers(dest="util_action", required=True)
    util_sub_subs.add_parser(
        "commit", help="Store current config to EEPROM")
    util_sub_subs.add_parser(
        "revert", help="Reset config to values stored in EEPROM")
    util_sub_subs.add_parser(
        "default", help="Reset config to hardcoded defaults")
    util_sub_subs.add_parser(
        "reset", help="Disconnect and restart UXIB device")
    util_sub_subs.add_parser(
        "dfu", help="Start DFU bootloader for firmware update")
    util_set_id = util_sub_subs.add_parser(
        "set_id", help="Change board ID")
    util_set_id.add_argument("set_id")
    util_ask = util_sub_subs.add_parser(
        "ask", help="Send raw command and read back response")
    util_ask.add_argument("ask_cmd")

    dio_sub = action_subs.add_parser("dio", help="Digital I/O actions")
    dio_sub_subs = dio_sub.add_subparsers(dest="dio_action", required=True)
    dio_sub_subs.add_parser(
        "list", help="Print list of terminal capabilities and current states")
    dio_get_dir = dio_sub_subs.add_parser(
        "get_dir", help="Get direction role (input / output) of terminal")
    dio_set_dir = dio_sub_subs.add_parser(
        "set_dir", help="Set direction role (input / output) of terminal")
    dio_get_input = dio_sub_subs.add_parser(
        "get_inp", help="Get logic state (1 / 0) of input")
    dio_get_output = dio_sub_subs.add_parser(
        "get_out", help="Get logic state (1 / 0) of output")
    dio_set_output = dio_sub_subs.add_parser(
        "set_out", help="Set logic state (1 / 0) of output")
    dio_pulse_output = dio_sub_subs.add_parser(
        "pulse_out",
        help="Pulse output to specified state for a specified time interval"
        )
    for sub in (dio_get_dir, dio_set_dir, dio_get_input, dio_get_output,
                dio_set_output, dio_pulse_output):
        sub.add_argument("term_no", type=int)
    for sub in (dio_set_output, dio_pulse_output):
        sub.add_argument("set_out", type=int, choices=[1, 0])
    dio_set_dir.add_argument("set_dir", choices=["in", "out"])
    dio_pulse_output.add_argument("length_s", type=float)

    flow_sub = action_subs.add_parser(
        "flow", help="Flow sensor actions")
    flow_sub_subs = flow_sub.add_subparsers(dest="flow_action", required=True)
    flow_sub_subs.add_parser(
        "info", help="Get flow measurement subsystem info")
    flow_sub_subs.add_parser(
        "list", help="List details of all flow sensor channels")
    flow_start = flow_sub_subs.add_parser(
        "start", help="Start flow measurement on specified channel(s)")
    flow_stop = flow_sub_subs.add_parser(
        "stop", help="Stop flow measurement on specified channel(s)")
    flow_raw = flow_sub_subs.add_parser(
        "raw", help="Print most recent raw sample")
    flow_sample = flow_sub_subs.add_parser(
        "sample", help="Print most recent sample, in physical units")
    flow_rate = flow_sub_subs.add_parser(
        "rate", help="Print most recent flow rate measurement")
    flow_rate = flow_sub_subs.add_parser(
        "log", help="Retrieve and print flow rate measurement history")
    flow_start_vol = flow_sub_subs.add_parser(
        "start_vol", help="Start a volume measurement on specified channel(s)")
    flow_stop_vol = flow_sub_subs.add_parser(
        "stop_vol",
        help="Stop and reset volume measurement on specified channel(s)"
        )
    flow_get_vol = flow_sub_subs.add_parser(
        "vol", help="Capture and print volume measurement results")
    for sub in (flow_start, flow_stop, flow_raw, flow_sample,
                flow_start_vol, flow_stop_vol, flow_get_vol):
        sub.add_argument(
            "flow_channels",
            type=parse_flow_channel_list,
            nargs="?",
            default=None
            )

    leak_sub = action_subs.add_parser(
        "leak", help="Leak detector actions")
    leak_sub_subs = leak_sub.add_subparsers(dest="leak_action", required=True)
    leak_sub_subs.add_parser(
        "list", help="List details of all leak detector channels")
    leak_set_detect = leak_sub_subs.add_parser(
        "set_detect", help="Set leak detection threshold")
    leak_set_short = leak_sub_subs.add_parser(
        "set_short", help="Set shorted sensor threshold")
    leak_set_open = leak_sub_subs.add_parser(
        "set_open", help="Set open sensor threshold")
    leak_raw = leak_sub_subs.add_parser(
        "raw", help="Print raw ADC readings")
    leak_status = leak_sub_subs.add_parser(
        "status", help="Print detection status")
    for sub in (leak_set_detect, leak_set_short, leak_set_open, leak_raw,
                leak_status):
        sub.add_argument(
            "leak_channels",
            type=parse_leak_channel_list,
            nargs="?",
            default=None
            )
    for param_name in ("detect", "short", "open"):
        sub = locals()[f'leak_set_{param_name}']
        sub.add_argument(f"{param_name}_thresh", type=int)

    #i2c_sub = action_subs.add_parser(
    #    "i2c", help="I2C control actions (NOT IMPLEMENTED)")
    # TODO

    for sub in (flow_raw, flow_sample, leak_raw, leak_status, flow_get_vol):
        sub.add_argument(
            "--watch",
            type=float,
            const=-1.,
            default=None,
            nargs="?",
            metavar="DELAY",
            help="Repeat continuously, only when new data comes in, with an "
                 "optional pause of DELAY seconds in between cycles"
            )

    return parser.parse_args(argv_rh)


def describe_channel_list(channels: Iterable[str]):
        ess = "s" if len(channels) > 1 else ""
        return f"channel{ess} " + ", ".join(channels)


def _print_connected_device_list():
    found_some = False
    print("Devices found:", file=sys.stderr)
    print("# port name, board ID, board model", file=sys.stderr)
    for portname, usb_loc, board_id, usb_vidpid, model_name \
            in UxibxxIoBoard.list_connected_devices(ext_info=True):
        print(f"{portname}, {board_id}, {model_name}")
        found_some = True
    if not found_some:
        print("(none)", file=sys.stderr)


def _print_board_info(board: UxibxxIoBoard):
    vid, pid = board.usb_vidpid
    print(f"Board ID          = {board.board_id}")
    print(f"Board model       = {board.board_model}")
    print(f"USB VID:PID       = {vid:04X}:{pid:04X}")
    print(f"USB port location = {board.usb_location}")
    print(f"Serial port name  = {board.serial_portname}")
    print(f"Driver features   = {','.join(board.features)}")
    print(f"FW version        = {board.board_fw_ver}")
    print(f"Remote API        = {'.'.join(str(x) for x in board.remote_api_ver)}")
    print(f"Sys clock res (s) = {board.seconds_per_tick:.3e}")
    print(f"Sys clock modulus = {board.tick_counter_modulus:d}")
    hrt_res_text = (
        f"{board.hrt_resolution_s:.3e}" if board.hrt_resolution_s
        else "(n/a)"
        )
    hrt_mod_text = (
        f"{board.hrt_modulus:d}" if board.hrt_modulus else "(n/a)")
    print(f"HRT res (s)       = {hrt_res_text}")
    print(f"HRT modulus       = {hrt_mod_text}")


def _print_dio_list(board: UxibxxIoBoard):
    print("# term no, supported modes, curr mode, in state, out state",
          file=sys.stderr)
    for term_no in board.terminal_nos:
        caps = []
        out_state = "x"
        in_state = "x"
        if term_no in board.input_nos:
            caps.append(board.IoDirection.INPUT.value)
            in_state = str(int(board.get_input(term_no)))
        if term_no in board.output_nos:
            caps.append(board.IoDirection.OUTPUT.value)
            out_state = str(int(board.get_output(term_no)))
        curr_dir = board.get_direction(term_no)
        print(
            f"{term_no:3d}, {' '.join(caps):>6s}, "
            f"{curr_dir.value:>3s}, {in_state:1s}, {out_state:1s}"
            )


def _print_flow_info(board: UxibxxIoBoard):
    print(f"Sensor channels   = {','.join(board.flow_sensor_channels)}")
    print(f"SS interval (s)   = {board.flow_ss_interval:.3e}")
    print(f"Totalizer modulus = {board.flow_totalizer_modulus:d}")


def _print_flow_sensor_list(board: UxibxxIoBoard):
    # TODO do we care about "sample interval" since it's not actually precisely fixed on SLF3?
    print(
        "# channel, sample interval (s), range (mL/minute), "
        "sensor family, product code, serial number",
        file=sys.stderr)
    for ch_name in board.flow_sensor_channels:
        if ch_name not in board.flow_sensors_available:
            continue
        info = board.flow_sensor_info[ch_name]
        sample_interval = board.flow_sample_interval[ch_name]
        range_min, range_max = board.flow_sensor_range[ch_name]
        print(
            f"{ch_name}, {sample_interval:.2e}, "
            f"{range_min:.2e}:{range_max:.2e}, {info.sensor_family}, "
            f"{info.sensor_prod_id}, {info.sensor_serial_no}"
            )


def _print_leak_channel_list(board: UxibxxIoBoard):
    print(
        "# channel, max val, sample interval (s), detect thresh, "
        "short thresh, open thresh",
        file=sys.stderr)
    for ch_name in board.leak_detector_channels:
        sample_intvl_s = board.get_leak_sample_interval(ch_name)
        detect_thresh = board.get_leak_detect_threshold(ch_name)
        short_thresh, open_thresh = board.get_leak_fault_thresholds(ch_name)
        max_adc_val = 1024 # TODO retrieve from HW
        print(
            f"{ch_name}, {max_adc_val}, {sample_intvl_s:.3e}, "
            f"{detect_thresh:6d}, {short_thresh:6d}, {open_thresh:6d}"
            )


def _check_for_feature(board: UxibxxIoBoard, feature_name: str):
    if feature_name not in board.features:
        print(
            f"{board.board_model} does not support "
            f"feature set: {feature_name}",
            file=sys.stderr
            )
        return False
    return True


def _handle_util_actions(board: UxibxxIoBoard, args: argparse.Namespace):
    match args.util_action:
        case "set_id":
            new_id = board.set_board_id(args.set_id)
            print(f"Board ID set to {new_id!r}.", file=sys.stderr)
        case "default":
            board.load_default_config()
            print(f"Configuration reset to default values.", file=sys.stderr)
        case "commit":
            board.commit_config()
            print(f"Configuration saved to EEPROM.", file=sys.stderr)
        case "revert":
            board.revert_config()
            print(
                f"Configuration reset to previous values stored in EEPROM.",
                file=sys.stderr
                )
        case "reset":
            board.reset_to_app()
            print(
                f"Board will perform a hardware reset shortly.",
                file=sys.stderr
                )
        case "dfu":
            board.reset_to_dfu()
            print(
                f"Board will enter DFU mode shortly.",
                file=sys.stderr
                )
        case "ask":
            ask_cmd = args.ask_cmd.strip()
            print(f"Query:    {ask_cmd!r}", file=sys.stderr)
            resp = board.ask_raw(args.ask_cmd)
            print(f"Response: {resp!r}", file=sys.stderr)
            print(resp)
        case _:
            # uhh
            return 1
    return 0


def _handle_dio_actions(board: UxibxxIoBoard, args: argparse.Namespace):
    if not _check_for_feature(board, "dio"):
        return 1
    match args.dio_action:
        case "list":
            _print_dio_list(board)
        case "get_dir" | "set_dir":
            if args.dio_action == "set_dir":
                board.set_direction(args.term_no, args.set_dir)
            print(
                f"dir({args.term_no})="
                f"{board.get_direction(args.term_no).value}"
                )
        case "get_out" | "set_out":
            if args.dio_action == "set_out":
                board.set_output(args.term_no, args.set_out)
            print(
                f"out({args.term_no})="
                f"{int(board.get_output(args.term_no))}"
                )
        case "get_inp":
            print(
                f"inp({args.term_no})="
                f"{int(board.get_input(args.term_no))}"
                )
        case "pulse_out":
            board.pulse_output(args.term_no, args.set_out, args.length_s)
            print(
                f"Pulsing output {args.term_no} to {args.set_out} "
                f"for {args.length_s:.3f} s.",
                file=sys.stderr
                )
        case _:
            # uhh
            return 1
    return 0


def _handle_flow_actions(board: UxibxxIoBoard, args: argparse.Namespace):
    # TODO make channel selection stuff a little less repetitive?
    if not _check_for_feature(board, "flow"):
        return 1
    match args.flow_action:
        case "info":
            _print_flow_info(board)
        case "list":
            _print_flow_sensor_list(board)
        case "start" | "stop":
            start = args.flow_action == "start"
            channels = board.enable_flow_measurement(
                channels=args.flow_channels, on=start)
            verb = "Started" if start else "Stopped"
            print(
                f"{verb} flow measurement on "
                f"{describe_channel_list(channels)}."
                )
        case "raw" | "sample":
            channels = (
                board.get_running_flow_channels()
                if args.flow_channels is None
                else args.flow_channels
                )
            if not channels:
                print("No channels selected!", file=sys.stderr)
                return 1
            flow_unit_desc, temp_unit_desc, time_unit_desc = (
                (" val", " val", "") if args.flow_action == "raw"
                else (" (mL/min)", " (deg C)", " (s)")
                )
            print(f"# channel, flow{flow_unit_desc}, "
                  f"temp{temp_unit_desc}, timestamp{time_unit_desc}, flags",
                  file=sys.stderr)
            while True:
                for ch_name in channels:
                    sample = (
                        board.get_last_flow_sample_raw
                        if args.flow_action == "raw" 
                        else board.get_last_flow_sample
                        )(ch_name)
                    if sample is None:
                        print(f"No data for channel {ch_name}", 
                              file=sys.stderr)
                        return 1
                    if args.flow_action == "raw":
                        print(
                            f"{ch_name}, {sample.flow_value:7d}, "
                            f"{sample.temp_value:7d}, "
                            f"0x{sample.ts_tick:016X}, "
                            f"{sample.flags.name}"
                            )
                    else:
                        print(
                            f"{ch_name}, {sample.ml_per_min:7.3f}, "
                            f"{sample.temp_degc:6.2f}, "
                            f"{sample.ts_s:11.3f}, "
                            f"{sample.flags.name}"
                            )
                if args.watch is None:
                    break
                elif args.watch > 0.:
                    time.sleep(args.watch)
        case "rate":
            for ch_name in args.flow_channels:
                ml_per_min = board.get_flow_rate(ch_name)
                print(f"rate({ch_name})={ml_per_min:.4f} mL/min")
        case "log":
            #print("# channel, end time (s), flow rate (mL/min), num missed",
            #      file=sys.stderr)
            print("Not yet implemented.")
            return 1
        case "start_vol" | "stop_vol":
            start = args.flow_action == "start_vol"
            channels = (
                board.flow_sensors_available if args.flow_channels is None
                else args.flow_channels
                )
            (
                board.start_vol_total if start else board.stop_vol_total
                )(channels)
            verb = "Started" if start else "Stopped"
            print(
                f"{verb} volume measurement on channels "
                f"{describe_channel_list(channels)}."
                )
        case "vol":
            print("# channel, elapsed time (s), flow (mL)",
                file=sys.stderr)
            while True:
                channels = (
                    board.get_vol_channels_running() if args.flow_channels is None
                    else args.flow_channels
                    )
                if not channels:
                    print("No volume measurements running.", file=sys.stderr)
                    break
                results = board.get_vol_total(channels, stop=False)
                for ch_name, result in results.items():
                    print(f"{ch_name}, {result.elapsed_s:9.3f}, "
                          f"{result.total_ml:9.3f}")
                if args.watch is None:
                    break
                elif args.watch > 0.:
                    time.sleep(args.watch)
        case _:
            # uhh
            return 1
    return 0


def _handle_leak_actions(board: UxibxxIoBoard, args: argparse.Namespace):
    if not _check_for_feature(board, "leak"):
        return 1
    channels = (
        board.leak_detector_channels
            if getattr(args, 'leak_channels', None) is None
        else args.leak_channels
        )
    match args.leak_action:
        case "list":
            _print_leak_channel_list(board)
        case "set_detect" | "set_short" | "set_open":
            param_name = args.leak_action.split("_", 1)[-1]
            thresh_val = getattr(args, f'{param_name}_thresh')
            setter_fn = getattr(board, f'set_leak_{param_name}_threshold')
            param_desc = {
                'detect': "Liquid detection",
                'short': "Short circuit",
                'open': "Open circuit"
                }[param_name]
            for ch_name in channels:
                new_val = setter_fn(ch_name, thresh_val)
                print(f"{param_desc} threshold for leak sensor channel "
                      f"{ch_name} set to {new_val}.")
        case "raw" | "status":
            if not channels:
                print("No channels selected!", file=sys.stderr)
                return 1
            last_tick = {}
            while True:
                for ch_name in channels:
                    result = (
                        board.get_leak_raw if args.leak_action == "raw"
                        else board.get_leak_status
                        )(ch_name)
                    if last_tick.get(ch_name, None) == result.ts_tick:
                        continue
                    result_desc = (
                        f"{result.ab},{result.ba}" if args.leak_action == "raw"
                        else result.status_name
                        )
                    print(f"{args.leak_action}({ch_name})={result_desc}")
                    last_tick[ch_name] = result.ts_tick
                if args.watch is None:
                    break
                elif args.watch > 0.:
                    time.sleep(args.watch)
        case _:
            # uhh
            return 1
    return 0


def cli_main(argv_rh: list[str]) -> int:
    args = parse_cli_args(argv_rh)
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
    if args.list:
        _print_connected_device_list()
        return 0
    try:
        if args.port:
            board = UxibxxIoBoard.from_serial_portname(args.port)
        elif args.bid:
            board = UxibxxIoBoard.from_board_id(args.bid)
        else:
            board = UxibxxIoBoard.open_first_device()
    except UxibxxIoBoard.DeviceNotFound as e:
        print(str(e), file=sys.stderr)
        return 1
    except serial.serialutil.SerialException as e:
        print(f"Couldn't open serial port {args.port!r}: {e}", file=sys.stderr)
        return 1
    print(
        f"Opened device: {board.board_id} ({board.board_model})",
        file=sys.stderr
        )

    match args.action_group:
        case "info":
            return _print_board_info(board)
        case "util":
            return _handle_util_actions(board, args)
        case "dio":
            return _handle_dio_actions(board, args)
        case "flow":
            return _handle_flow_actions(board, args)
        case "leak":
            return _handle_leak_actions(board, args)
        case _:
            print("Nothing to do (try --help).", file=sys.stderr)
    return 0


def _cli_entry():
    sys.exit(cli_main(sys.argv[1:]))
