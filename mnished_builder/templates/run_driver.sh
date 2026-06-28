#!/bin/bash
# Invoke driver.py with the Python interpreter that has both mnished and
# dakota.interfacing installed (set scaffold.driver_python in the watershed
# config; defaults to `python`).
MNISHED_BUILDER_DRIVER_PYTHON driver.py "$@"
