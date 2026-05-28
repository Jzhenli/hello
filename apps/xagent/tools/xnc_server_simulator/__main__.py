#!/usr/bin/env python
"""XNC Server Simulator - Main entry point"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from xagent.tools.xnc_server_simulator.app import run_app

if __name__ == "__main__":
    run_app()
