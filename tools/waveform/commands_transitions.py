"""Subcommand: dump value transitions for specified signals."""

import sys

from loader import load_vcd
from signal_match import match_signals
from formatting import parse_value


def cmd_transitions(args):
    """Dump value transitions for specified signals."""
    vcd = load_vcd(args.file)
    matched = match_signals(vcd.signals, args.signals)

    if not matched:
        print("No matching signals found.", file=sys.stderr)
        sys.exit(1)

    for sig_name in matched:
        tv = vcd[sig_name].tv
        print(f"\n--- {sig_name} ---")
        count = 0
        for t, val in tv:
            if args.max and count >= args.max:
                print(f"  ... ({len(tv) - args.max} more)")
                break
            t_ns = t / 1000 if t >= 1000 else t
            unit = "ns" if t >= 1000 else "ps"
            formatted = parse_value(val, args.format)
            print(f"  {t_ns:>10.1f}{unit}: {formatted}")
            count += 1
