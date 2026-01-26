import time

from uxibxx import UxibxxIoBoard


ioboard = UxibxxIoBoard.from_board_id("4D8502")
# ...or UxibxxIoBoard.from_serial_portname("COM2")
# ...or UxibxxIoBoard.open_first_device()
print(f"Model: {ioboard.board_model}")
print(f"Serial no: {ioboard.board_id}")

# Print state of inputs
print()
for i in ioboard.input_nos:
    print(f"Input {i} is {ioboard.get_input(i)}")

# Flash each output in sequence
for i in ioboard.output_nos:
    ioboard.set_output(i, True)
    time.sleep(0.25)
    ioboard.set_output(i, False)
    time.sleep(0.1)
