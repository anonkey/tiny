"""Subcommand: sample signals at regular intervals or on clock edges."""

import sys

from loader import load_vcd
from signal_match import match_signals
from formatting import parse_value


def cmd_table(args):
    """Sample signals at regular intervals or on clock edges."""
    vcd = load_vcd(args.file)
    matched = match_signals(vcd.signals, args.signals)

    if not matched:
        print("No matching signals found.", file=sys.stderr)
        sys.exit(1)

    # Determine sample times
    if args.clock:
        clock_matches = match_signals(vcd.signals, [args.clock])
        if not clock_matches:
            print(f"Clock signal '{args.clock}' not found.", file=sys.stderr)
            sys.exit(1)
        clk_tv = vcd[clock_matches[0]].tv
        sample_times = []
        prev_val = "0"
        for t, val in clk_tv:
            if args.edge == "rising" and prev_val == "0" and val == "1":
                sample_times.append(t)
            elif args.edge == "falling" and prev_val == "1" and val == "0":
                sample_times.append(t)
            elif args.edge == "both" and val != prev_val and val in ("0", "1"):
                sample_times.append(t)
            prev_val = val
    else:
        # Find time range from all matched signals
        max_time = 0
        for sig_name in matched:
            tv = vcd[sig_name].tv
            if tv:
                max_time = max(max_time, tv[-1][0])
        step = args.step * 1000  # ns to ps
        if step <= 0:
            step = max_time // 50 if max_time > 0 else 1000
        sample_times = list(range(0, max_time + 1, step))

    if args.max:
        sample_times = sample_times[:args.max]

    # Print header
    short_names = []
    for s in matched:
        parts = s.split(".")
        short = parts[-1] if len(parts) > 1 else s
        if len(short) > 20:
            short = short[:17] + "..."
        short_names.append(short)

    header = f"{'Time':>10}"
    for name in short_names:
        header += f"  {name:>20}"
    print(header)
    print("-" * len(header))

    # Print rows
    for t in sample_times:
        t_ns = t / 1000 if t >= 1000 else t
        row = f"{t_ns:>9.0f}ns"
        for sig_name in matched:
            val = vcd[sig_name][t]
            formatted = parse_value(val, args.format)
            row += f"  {formatted:>20}"
        print(row)
