# `uxibxx` package
This is the Python driver for UXIB*xx* I/O boards.

## API documentation
Refer to the docstrings or compiled documentation for API usage information. 

The API documentation is built using Sphinx. To view the docs as HTML, run `make html` from the `driver/docs/` subdirectory of this source distribution, then open `driver/docs/html/_build/index.html` in a web browser. Other formats are available as well; run `make` with no arguments for a list.

The content of the usage example from the documentation can also be found directly at `driver/docs/usage_example.py`.

## Requirements
The `uxibxx` package requires:
- Python >= 3.10
- `pyserial` >= 3.5 (earlier versions may work, not tested).

Building the documentation additionally requires `sphinx` and GNU Make.

## Installation
Activate a virtual environment if desired, then, from the root of this source distribution, run:
```
pip install .
```

## Support
This repository is maintained by Greg Courville of the Bioengineering Platform at Chan Zuckerberg Biohub San Francisco.
