#!/usr/bin/env python
"""XNC Server Simulator - Standalone launcher

This script can be run directly to start the XNC Server Simulator.

Usage:
    python run_xnc_simulator.py

Or with module:
    cd apps/xagent/tools/xnc_server_simulator
    python app.py
"""

import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
simulator_dir = os.path.join(script_dir, "xnc_server_simulator")
src_path = os.path.normpath(os.path.join(script_dir, "..", "src"))

if os.path.exists(src_path):
    sys.path.insert(0, src_path)

sys.path.insert(0, simulator_dir)

from app import run_app

if __name__ == "__main__":
    run_app()
