# uxibxx-io-board
## Introduction
This repository contains the hardware design data, firmware and a Python driver implementation for the UXIB*xx* "family" of digital I/O board~~s~~. This project is intended to provide minimum-friction tools for interfacing Python code to electrical stuff (turning loads on and off, reading switches, etc) in laboratory automation projects.

Currently the device "family" consists of a single example, UXIB-DN12, designed to control a bank of 12 loads such as solenoid valves.

## Directory contents
- `driver/` contains the `uxibxx` Python package used to control UXIB*xx* devices
- `firmware/` contains the source code for the AVR firmware
- `pcb/` contains the KiCAD EDA project files for the UXIB-DN12 PCB

## Getting started
If starting with an already-made UXIB*xx* device, just install the included `uxibxx` package and review the associated API documentation. No extra system-level driver is required on Windows, MacOS or Linux.

See the `README.md` in each subdirectory for further information.

## Licenses
Software source code is licensed under the BSD 3-Clause License. Hardware design files are licensed under CERN-OHL-W.
See the `LICENSE` file in each subdirectory for a copy of the applicable license terms.
