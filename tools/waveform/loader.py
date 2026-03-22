"""VCD/FST file loading with vcdvcd."""

import os
import sys

try:
    import vcdvcd
except ImportError:
    print("error: vcdvcd not installed. Run: pip install vcdvcd", file=sys.stderr)
    sys.exit(1)


def load_vcd(path):
    """Load a VCD/FST file with a clear error on binary FST format."""
    try:
        return vcdvcd.VCDVCD(path)
    except UnicodeDecodeError:
        print(f"error: '{os.path.basename(path)}' is binary FST format (not readable by vcdvcd).", file=sys.stderr)
        print("  Regenerate the trace without the -fst flag in the Makefile,", file=sys.stderr)
        print("  or use $dumpfile(\"name.vcd\") in the testbench.", file=sys.stderr)
        sys.exit(1)


def is_1bit(vcd, sig_name):
    """Check if a signal is 1-bit wide."""
    sig_id = vcd.references_to_ids.get(sig_name)
    if sig_id and sig_id in vcd.data:
        return int(vcd.data[sig_id].size) == 1
    return False
