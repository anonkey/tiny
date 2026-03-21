#!/usr/bin/env python3
"""Project manager — dispatches to tools/manager/manager.py."""

import os
import subprocess
import sys

MANAGER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "manager", "manager.py")
sys.exit(subprocess.call([sys.executable, MANAGER] + sys.argv[1:]))
