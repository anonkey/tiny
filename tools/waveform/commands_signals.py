"""Subcommand: list all signals in a trace file."""

import re
import sys

from loader import load_vcd


def cmd_signals(args):
    """List all signals in the trace file."""
    vcd = load_vcd(args.file)
    signals = sorted(vcd.signals)

    if args.filter:
        pattern = re.compile(args.filter, re.IGNORECASE)
        signals = [s for s in signals if pattern.search(s)]

    for s in signals[:args.max or len(signals)]:
        print(s)

    print(f"\n{len(signals)} signal(s)", file=sys.stderr)
