#!/usr/bin/env python3
"""Generic waveform analysis tool for FST/VCD trace files.

Subcommands:
    signals      List all signals in a trace file
    transitions  Dump value changes for specific signals
    table        Sample signals at regular intervals or clock edges
    wave         Render signals as Unicode waveforms in the terminal

The file argument can be a module name (e.g. "spi", "half_cpu", "pc")
instead of a full path. The tool resolves it to test/tb_<module>.fst
automatically. If ambiguous, it prompts for interactive selection.

Examples:
    python tools/waveform/waveform.py signals spi
    python tools/waveform/waveform.py signals half_cpu --filter "pc|state"
    python tools/waveform/waveform.py transitions spi "rx_done" "sclk" --max 10
    python tools/waveform/waveform.py table half_cpu "pc_out" "state" --step 10
    python tools/waveform/waveform.py table half_cpu "pc_out" --clock clk --edge rising
    python tools/waveform/waveform.py wave spi "sclk" "mosi" "cs_n" "rx_done"
    python tools/waveform/waveform.py wave half_cpu "clk" "state" "pc_out" --width 100
"""

import argparse
import fnmatch
import glob
import os
import re
import sys

try:
    import vcdvcd
except ImportError:
    print("error: vcdvcd not installed. Run: pip install vcdvcd", file=sys.stderr)
    sys.exit(1)


# --- Project root detection ---

def find_project_root():
    """Walk up from script location to find the project root (contains src/ and test/)."""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        if os.path.isdir(os.path.join(d, "src")) and os.path.isdir(os.path.join(d, "test")):
            return d
        d = os.path.dirname(d)
    return os.getcwd()


PROJECT_ROOT = find_project_root()
TEST_DIR = os.path.join(PROJECT_ROOT, "test")


# --- Module name → FST file resolution ---

def list_available_modules():
    """Scan test/ and test/artifacts/ for tb_*.fst files and return module names."""
    modules = {}
    # Search test/, test/artifacts/, and test/*/ for FST files
    patterns = [
        os.path.join(TEST_DIR, "tb_*.fst"),
        os.path.join(TEST_DIR, "artifacts", "tb_*.fst"),
        os.path.join(TEST_DIR, "*", "tb_*.fst"),
    ]
    for pat in patterns:
        for fst in sorted(glob.glob(pat)):
            basename = os.path.basename(fst)
            module = basename.removeprefix("tb_").removesuffix(".fst")
            # Prefer files closer to test/ root (don't overwrite)
            if module not in modules:
                modules[module] = fst
    # Also check for tb.fst (the top-level)
    for d in [TEST_DIR, os.path.join(TEST_DIR, "artifacts")]:
        top_fst = os.path.join(d, "tb.fst")
        if os.path.isfile(top_fst):
            modules["top"] = top_fst
            break
    return modules


def interactive_select(prompt, options):
    """Let the user pick from a numbered list. Returns selected value."""
    print(prompt, file=sys.stderr)
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt}", file=sys.stderr)
    while True:
        try:
            choice = input("choice [1]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("", file=sys.stderr)
            sys.exit(1)
        if not choice:
            return options[0]
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass
        print(f"  enter 1-{len(options)}", file=sys.stderr)


def resolve_file(file_arg):
    """Resolve a file argument: either a path or a module name."""
    # If it's an existing file, use it directly
    if os.path.isfile(file_arg):
        return file_arg

    # Try as a path relative to project root
    rel = os.path.join(PROJECT_ROOT, file_arg)
    if os.path.isfile(rel):
        return rel

    # Treat as module name
    modules = list_available_modules()

    # Exact match
    if file_arg in modules:
        return modules[file_arg]

    # Fuzzy: find modules containing the argument
    candidates = {m: p for m, p in modules.items() if file_arg in m}

    if len(candidates) == 1:
        name, path = next(iter(candidates.items()))
        print(f"→ {name} ({os.path.relpath(path, PROJECT_ROOT)})", file=sys.stderr)
        return path

    if len(candidates) > 1:
        names = list(candidates.keys())
        selected = interactive_select(f"Multiple modules match '{file_arg}':", names)
        return candidates[selected]

    # Nothing found — list available
    if modules:
        print(f"No module matching '{file_arg}'. Available modules:", file=sys.stderr)
        for m in sorted(modules):
            print(f"  {m}", file=sys.stderr)
    else:
        print(f"No FST files found in {TEST_DIR}", file=sys.stderr)
    sys.exit(1)


# --- Signal matching with interactive selection ---

def match_signals(all_signals, patterns, interactive=True):
    """Match signal names against patterns. Prompts interactively if too many matches."""
    matched = []
    for pat in patterns:
        # Exact full-path match
        if pat in all_signals:
            matched.append(pat)
            continue

        # Exact leaf-name match (e.g. "clk" matches "tb.dut.clk" but not "tb.dut.sclk")
        leaf_exact = sorted(
            s for s in all_signals if s.rsplit(".", 1)[-1] == pat
        )
        if leaf_exact:
            # Prefer the shallowest (top-level) match
            leaf_exact.sort(key=lambda s: (s.count("."), s))
            if len(leaf_exact) == 1 or not interactive:
                matched.extend(leaf_exact[:1] if interactive else leaf_exact)
                continue
            # Multiple exact leaf matches — pick shallowest automatically
            matched.append(leaf_exact[0])
            continue

        # Glob match
        found = sorted(s for s in all_signals if fnmatch.fnmatch(s, pat))
        if found:
            matched.extend(found)
            continue

        # Substring match on leaf name first, then full path
        leaf_sub = sorted(
            s for s in all_signals if pat in s.rsplit(".", 1)[-1]
        )
        found = leaf_sub if leaf_sub else sorted(s for s in all_signals if pat in s)
        if not found:
            print(f"warning: no signal matching '{pat}'", file=sys.stderr)
            continue

        # If many matches and interactive, let user select
        if interactive and len(found) > 10:
            found.sort(key=lambda s: (s.count("."), s))
            top = found[:20]
            print(f"'{pat}' matches {len(found)} signals. Showing top {len(top)}:", file=sys.stderr)
            selected = interactive_select("Select signal:", top)
            matched.append(selected)
        else:
            matched.extend(found)

    # Deduplicate preserving order
    seen = set()
    result = []
    for s in matched:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


# --- Value formatting ---

def parse_value(raw, fmt):
    """Convert a raw binary string value to the requested format."""
    if raw in ("x", "X", "z", "Z"):
        return raw
    try:
        n = int(raw, 2) if all(c in "01" for c in raw) else int(raw)
    except ValueError:
        return raw
    if fmt == "bin":
        return f"0b{n:b}"
    elif fmt == "dec":
        return str(n)
    else:
        return f"0x{n:X}"


# --- File loading ---

def load_vcd(path):
    """Load a VCD/FST file with a clear error on binary FST format."""
    try:
        return vcdvcd.VCDVCD(path)
    except UnicodeDecodeError:
        print(f"error: '{os.path.basename(path)}' is binary FST format (not readable by vcdvcd).", file=sys.stderr)
        print("  Regenerate the trace without the -fst flag in the Makefile,", file=sys.stderr)
        print("  or use $dumpfile(\"name.vcd\") in the testbench.", file=sys.stderr)
        sys.exit(1)


# --- Subcommands ---

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


# --- Waveform rendering ---

def is_1bit(vcd, sig_name):
    """Check if a signal is 1-bit wide."""
    sig_id = vcd.references_to_ids.get(sig_name)
    if sig_id and sig_id in vcd.data:
        return int(vcd.data[sig_id].size) == 1
    return False


def build_slot_map(all_signals_tv, t_start, t_end, cols, fmt="hex"):
    """Build a non-linear time→column mapping sized to fit value labels.

    Collects all transitions from all signals. Each slot is sized to fit
    its widest value label. If too many transitions to fit, shows the first N.

    Returns: sorted list of times, and a function time→col.
    """
    # Collect all transition times where value actually changed
    times_set = set()
    sig_vals = []  # per-signal: list of (time, formatted_value)
    for tv in all_signals_tv:
        vals = []
        prev_val = None
        for t, v in tv:
            if t < t_start:
                prev_val = v
                continue
            if t > t_end:
                break
            if v != prev_val:
                times_set.add(t)
                vals.append((t, parse_value(v, fmt)))
                prev_val = v
        sig_vals.append(vals)
    times_set.add(t_start)
    times = sorted(times_set)

    if len(times) <= 1:
        return times, lambda t: 0

    # For each slot, find the max label width across all signals
    slot_widths = []
    for idx in range(len(times)):
        max_label = 0
        for sv in sig_vals:
            label = ""
            for t, lbl in sv:
                if t <= times[idx]:
                    label = lbl
                else:
                    break
            if len(label) > max_label:
                max_label = len(label)
        # Minimum: 2 cols (transition + 1 char); with label: marker + pad + label + pad
        width = max(2, max_label + 3) if max_label > 0 else 2
        slot_widths.append(width)

    # Trim slots that don't fit
    total = 0
    n_fit = 0
    for w in slot_widths:
        if total + w > cols:
            break
        total += w
        n_fit += 1
    if n_fit < 1:
        n_fit = 1
    times = times[:n_fit]
    slot_widths = slot_widths[:n_fit]

    # Distribute remaining columns evenly
    total_min = sum(slot_widths)
    extra = cols - total_min
    if extra > 0:
        per_slot = extra // len(slot_widths)
        remainder = extra % len(slot_widths)
        for i in range(len(slot_widths)):
            slot_widths[i] += per_slot + (1 if i < remainder else 0)

    # Build mapping: cumulative column positions
    time_to_col = {}
    col = 0
    for i, tm in enumerate(times):
        time_to_col[tm] = col
        col += slot_widths[i]

    def map_time(t):
        if t <= times[0]:
            return 0
        if t >= times[-1]:
            return time_to_col[times[-1]]
        lo, hi = 0, len(times) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if times[mid] <= t:
                lo = mid
            else:
                hi = mid - 1
        return time_to_col[times[lo]]

    return times, map_time


def render_1bit(tv, t_start, t_end, cols, map_time=None):
    """Render a 1-bit signal as Unicode waveform characters."""
    if not tv:
        return "_" * cols

    row = []

    # Build sorted transitions within range
    vals = []  # (col_index, value) for each transition
    prev_val = "0"
    for t, v in tv:
        if t < t_start:
            prev_val = v
            continue
        if t > t_end:
            break
        if map_time:
            col = map_time(t)
        else:
            ps_per_col = (t_end - t_start) / cols if cols > 0 else 1
            col = int((t - t_start) / ps_per_col)
        col = min(col, cols - 1)
        vals.append((col, v))
    start_val = prev_val

    # Fill columns
    cur_val = start_val
    transition_at = {}  # col -> new_value
    for col, v in vals:
        transition_at[col] = v

    for c in range(cols):
        if c in transition_at:
            new_val = transition_at[c]
            if cur_val in ("0", "x", "X", "z", "Z") and new_val == "1":
                row.append("\u2571")  # ╱ rising
            elif cur_val == "1" and new_val in ("0", "x", "X", "z", "Z"):
                row.append("\u2572")  # ╲ falling
            else:
                row.append("\u2594" if new_val == "1" else "_")
            cur_val = new_val
        else:
            row.append("\u2594" if cur_val == "1" else "_")  # ▔ or _

    return "".join(row)


def render_multibit(tv, t_start, t_end, cols, fmt, map_time=None):
    """Render a multi-bit signal as 3 lines: top rail, value, bottom rail.

    Returns a tuple of 3 strings (top, mid, bot), each `cols` characters wide.
        ╥───────╥───────╥──────
        ║ 0x0   ║ 0x9   ║ 0x1
        ╨───────╨───────╨──────
    """
    if not tv:
        top = "\u2500" * cols
        mid = " " * cols
        bot = "\u2500" * cols
        return (top, mid, bot)

    # Build segments: (start_col, end_col, formatted_label)
    # Only create a new segment when the value actually changes
    segments = []
    prev_val = "0"
    prev_col = 0

    for t, v in tv:
        if t < t_start:
            prev_val = v
            continue
        if t > t_end:
            break
        # Skip if value didn't change
        if v == prev_val and segments:
            continue
        if map_time:
            col = map_time(t)
        else:
            ps_per_col = (t_end - t_start) / cols if cols > 0 else 1
            col = int((t - t_start) / ps_per_col)
        col = min(col, cols - 1)
        if col > prev_col or not segments:
            segments.append((prev_col, col, parse_value(prev_val, fmt)))
            prev_col = col
        prev_val = v

    # Last segment to end
    if prev_col < cols:
        segments.append((prev_col, cols, parse_value(prev_val, fmt)))

    # Merge consecutive segments with the same label
    merged = []
    for start, end, label in segments:
        if merged and merged[-1][2] == label:
            # Extend previous segment (drop the transition between them)
            merged[-1] = (merged[-1][0], end, label)
        else:
            merged.append((start, end, label))
    segments = merged

    # Render 3 rows
    top = [" "] * cols
    mid = [" "] * cols
    bot = [" "] * cols

    for start, end, label in segments:
        width = end - start
        if width <= 0:
            continue

        off = 0
        if start > 0:
            top[start] = "\u2565"  # ╥
            mid[start] = "\u2551"  # ║
            bot[start] = "\u2568"  # ╨
            off = 1

        # Fill rails and center label
        inner = width - off
        for i in range(off, width):
            if start + i < cols:
                top[start + i] = "\u2500"  # ─
                bot[start + i] = "\u2500"  # ─

        # Truncate label if needed to fit
        shown = label
        if len(shown) > inner:
            shown = label[:max(1, inner)]
        if inner >= 1:
            pad_total = inner - len(shown)
            pad_l = pad_total // 2
            for j, ch in enumerate(shown):
                pos = start + off + pad_l + j
                if pos < cols:
                    mid[pos] = ch

    return ("".join(top), "".join(mid), "".join(bot))


def format_time(t, base_unit):
    """Format a time value with auto-scaling (ps → ns → us → ms)."""
    scales = [("ps", 1), ("ns", 1e3), ("us", 1e6), ("ms", 1e9)]
    if base_unit == "ns":
        scales = [("ns", 1), ("us", 1e3), ("ms", 1e6)]
    elif base_unit == "us":
        scales = [("us", 1), ("ms", 1e3)]

    # Pick the largest unit where the value is >= 1
    unit, factor = scales[0]
    for u, f in scales:
        if abs(t) >= f or f == 1:
            unit, factor = u, f
    val = t / factor
    if val == int(val):
        return f"{int(val)}{unit}"
    return f"{val:.1f}{unit}"


def render_time_axis(t_start, t_end, cols, time_unit="ns", slot_times=None, map_time=None):
    """Render a time axis with tick marks, preventing label overlap."""
    axis = [" "] * cols

    # Build candidate ticks: (col, label) pairs
    ticks = []
    if slot_times and map_time and len(slot_times) > 1:
        num_ticks = min(10, cols // 12)
        if num_ticks < 2:
            num_ticks = 2
        n = len(slot_times)
        step = max(1, n // num_ticks)
        tick_indices = list(range(0, n, step))
        if tick_indices[-1] != n - 1:
            tick_indices.append(n - 1)
        for idx in tick_indices:
            t = slot_times[idx]
            col = map_time(t)
            ticks.append((col, format_time(t, time_unit)))
    else:
        num_ticks = min(10, cols // 12)
        if num_ticks < 2:
            num_ticks = 2
        for i in range(num_ticks + 1):
            col = int(i * (cols - 1) / num_ticks)
            t = t_start + i * (t_end - t_start) / num_ticks
            ticks.append((col, format_time(t, time_unit)))

    # Place ticks, skipping any that would overlap the previous label
    next_free = 0
    for col, label in ticks:
        if col < next_free:
            continue
        if col < cols:
            axis[col] = "|"
        start = col + 1
        for j, ch in enumerate(label):
            pos = start + j
            if pos < cols:
                axis[pos] = ch
        next_free = col + 1 + len(label) + 1  # +1 gap after label

    return "".join(axis)


def cmd_wave(args):
    """Render signals as Unicode waveforms."""
    vcd = load_vcd(args.file)

    if args.signals:
        matched = match_signals(vcd.signals, args.signals)
    else:
        # No signals specified — show all top-level signals
        # Find the shallowest hierarchy depth and show all signals at that level
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

    # Get time unit from VCD timescale
    time_unit = vcd.timescale.get("unit", "ns") if vcd.timescale else "ns"

    # --start/--end are in the file's native time unit
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

    # Signal name column
    short_names = []
    for s in matched:
        parts = s.split(".")
        short = parts[-1] if len(parts) > 1 else s
        short_names.append(short)
    name_width = max(len(n) for n in short_names) + 2
    wave_cols = total_width - name_width - 1  # -1 for separator

    if wave_cols < 10:
        print("Terminal too narrow for waveform display.", file=sys.stderr)
        sys.exit(1)

    # Use multi-bit signals to drive the slot map layout
    # (1-bit signals like clk toggle too fast and would eat all columns)
    # 1-bit signals still render correctly within the layout
    multibit_tv = [vcd[s].tv for s in matched if not is_1bit(vcd, s)]
    all_tv = [vcd[s].tv for s in matched]

    # Limit transitions if requested
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

    # Build slot map from multi-bit signals (or all if no multi-bit)
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


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(
        description="Waveform analysis tool — use module names or file paths",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # signals
    p_sig = sub.add_parser("signals", help="List all signals in a trace file")
    p_sig.add_argument("file", help="Module name (e.g. 'spi') or path to FST/VCD file")
    p_sig.add_argument("--filter", "-f", help="Regex filter for signal names")
    p_sig.add_argument("--max", "-n", type=int, default=0, help="Max signals to show")

    # transitions
    p_tr = sub.add_parser("transitions", help="Dump value changes for signals")
    p_tr.add_argument("file", help="Module name (e.g. 'spi') or path to FST/VCD file")
    p_tr.add_argument("signals", nargs="+", help="Signal names (exact, glob, or substring)")
    p_tr.add_argument("--max", "-n", type=int, default=0, help="Max transitions per signal")
    p_tr.add_argument("--format", choices=["hex", "bin", "dec"], default="hex")

    # table
    p_tbl = sub.add_parser("table", help="Sample signals at intervals or clock edges")
    p_tbl.add_argument("file", help="Module name (e.g. 'spi') or path to FST/VCD file")
    p_tbl.add_argument("signals", nargs="+", help="Signal names (exact, glob, or substring)")
    p_tbl.add_argument("--step", "-s", type=int, default=10, help="Sample interval in ns")
    p_tbl.add_argument("--clock", "-c", help="Clock signal (sample on edges)")
    p_tbl.add_argument("--edge", choices=["rising", "falling", "both"], default="rising")
    p_tbl.add_argument("--max", "-n", type=int, default=0, help="Max rows")
    p_tbl.add_argument("--format", choices=["hex", "bin", "dec"], default="hex")

    # wave
    p_wave = sub.add_parser("wave", help="Render signals as Unicode waveforms")
    p_wave.add_argument("file", help="Module name (e.g. 'spi') or path to FST/VCD file")
    p_wave.add_argument("signals", nargs="*", help="Signal names (omit to show all top-level signals)")
    p_wave.add_argument("--width", "-w", type=int, default=0, help="Total display width (default: terminal width)")
    p_wave.add_argument("--max", "-n", type=int, default=0, help="Max transitions to render")
    p_wave.add_argument("--format", choices=["hex", "bin", "dec"], default="hex")
    p_wave.add_argument("--start", type=float, default=None, help="Start time in ns")
    p_wave.add_argument("--end", type=float, default=None, help="End time in ns")

    args = parser.parse_args()

    # Resolve module name → file path
    args.file = resolve_file(args.file)

    if args.command == "signals":
        cmd_signals(args)
    elif args.command == "transitions":
        cmd_transitions(args)
    elif args.command == "table":
        cmd_table(args)
    elif args.command == "wave":
        cmd_wave(args)


if __name__ == "__main__":
    main()
