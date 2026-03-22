"""Subcommand: render signals as Unicode waveforms in the terminal."""

import os
import sys

from loader import load_vcd, is_1bit
from signal_match import match_signals
from render import build_slot_map, render_1bit, render_multibit, render_time_axis


def cmd_wave(args):
    """Render signals as Unicode waveforms."""
    vcd = load_vcd(args.file)

    if args.signals:
        matched = match_signals(vcd.signals, args.signals)
    else:
        if not vcd.signals:
            print("No signals in trace.", file=sys.stderr)
            sys.exit(1)
        min_depth = min(s.count(".") for s in vcd.signals)
        matched = sorted(s for s in vcd.signals if s.count(".") == min_depth)

    if not matched:
        print("No matching signals found.", file=sys.stderr)
        sys.exit(1)

    # Determine time range
    t_start = 0
    t_end = 0
    for sig_name in matched:
        tv = vcd[sig_name].tv
        if tv:
            t_end = max(t_end, tv[-1][0])

    time_unit = vcd.timescale.get("unit", "ns") if vcd.timescale else "ns"

    if args.start is not None:
        t_start = args.start
    if args.end is not None:
        t_end = args.end

    if t_end <= t_start:
        print("No data in time range.", file=sys.stderr)
        sys.exit(1)

    # Determine widths
    try:
        term_width = os.get_terminal_size().columns
    except OSError:
        term_width = 80
    total_width = args.width or term_width

    short_names = []
    for s in matched:
        parts = s.split(".")
        short = parts[-1] if len(parts) > 1 else s
        short_names.append(short)
    name_width = max(len(n) for n in short_names) + 2
    wave_cols = total_width - name_width - 1

    if wave_cols < 10:
        print("Terminal too narrow for waveform display.", file=sys.stderr)
        sys.exit(1)

    multibit_tv = [vcd[s].tv for s in matched if not is_1bit(vcd, s)]
    all_tv = [vcd[s].tv for s in matched]

    if args.max:
        all_times = set()
        for tv in (multibit_tv or all_tv):
            prev_val = None
            for t, v in tv:
                if t_start <= t <= t_end and v != prev_val:
                    all_times.add(t)
                    prev_val = v
        sorted_times = sorted(all_times)
        if len(sorted_times) > args.max:
            t_end = sorted_times[args.max - 1]

    slot_times, map_time = build_slot_map(multibit_tv or all_tv, t_start, t_end, wave_cols, args.format)

    # Render each signal
    pad = " " * name_width
    for sig_name, short in zip(matched, short_names):
        tv = vcd[sig_name].tv
        label = f"{short:<{name_width}}"
        if is_1bit(vcd, sig_name):
            wave = render_1bit(tv, t_start, t_end, wave_cols, map_time)
            print(f"{label}\u2502{wave}")
        else:
            top, mid, bot = render_multibit(tv, t_start, t_end, wave_cols, args.format, map_time)
            print(f"{pad}\u2502{top}")
            print(f"{label}\u2502{mid}")
            print(f"{pad}\u2502{bot}")

    # Time axis
    padding = " " * name_width
    axis = render_time_axis(t_start, t_end, wave_cols, time_unit, slot_times, map_time)
    print(f"{padding}\u2502{axis}")
