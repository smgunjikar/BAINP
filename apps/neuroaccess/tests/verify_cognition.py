"""Compatibility entry point: the old exposure-only C01 is retired.
Runs the current Core battery and NeuroAccess regression checks instead.
"""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name('verify_battery.py')),run_name='__main__')
