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
import os
import sys

# Ensure the waveform package directory is on sys.path so sibling modules
# can be imported when this script is invoked directly.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from resolution import resolve_file
from commands_signals import cmd_signals
from commands_transitions import cmd_transitions
from commands_table import cmd_table
from commands_wave import cmd_wave


def main():
    parser = argparse.ArgumentParser(
        description="Waveform analysis tool \u2014 use module names or file paths",
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

    # Resolve module name -> file path
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
