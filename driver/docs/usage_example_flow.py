from uxibxx import UxibxxIoBoard


shf4 = UxibxxIoBoard.from_board_id("DEMO-SH4")
flow_channels = shf4.enable_flow_measurement()
print(f"Channels running: {flow_channels}")
shf4.start_vol_total("AB")
# (now move some fluid in channels A and B)
results = shf.get_vol_total("AB")
print(
	f"Moved {results['A'].total_ml:.2f} mL in ch A "
	f"and {results['A'].total_ml:.2f} mL in ch B"
	)
