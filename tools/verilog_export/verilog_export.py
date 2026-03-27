#!/usr/bin/env python3
"""Export Verilog modules to CircuitVerse JSON via Yosys synthesis.

Usage:
    python verilog_export.py half_cpu                                    # CircuitVerse (high-level via Yosys, flat)
    python verilog_export.py half_cpu --gate                             # CircuitVerse (gate-level via Yosys)
    python verilog_export.py mux -f circuitverse-yosys-hier             # CircuitVerse (high-level via Yosys, hierarchical)
    python verilog_export.py half_cpu -o out/                            # custom output directory
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_MANAGER_DIR: str = os.path.join(os.path.dirname(_SCRIPT_DIR), "manager")
if _MANAGER_DIR not in sys.path:
    sys.path.insert(0, _MANAGER_DIR)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from manager_utils import discover_modules, find_project_root, resolve_deps

from synthesis.hierarchical import generate_circuitverse_yosys, generate_circuitverse_yosys_hier

_FORMATS: list[str] = ["circuitverse-yosys", "circuitverse-yosys-hier"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export Verilog modules to CircuitVerse JSON via Yosys."
    )
    parser.add_argument("module", help="Module name (resolved via manager.json)")
    parser.add_argument(
        "-f", "--format", default="circuitverse-yosys", choices=_FORMATS,
        help="Output format (default: circuitverse-yosys)",
    )
    parser.add_argument("-o", "--output", default="", help="Output directory (default: module's export/ subdir)")
    parser.add_argument(
        "-g", "--gate", action="store_true",
        help="Force gate-level synthesis (for circuitverse-yosys and circuitverse-yosys-hier)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "-c", "--check", action="store_true",
        help="Run routing verification after export",
    )
    parser.add_argument(
        "--cache", action="store_true",
        help="Cache routed module scopes for faster repeated hier exports",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(name)s: %(levelname)s: %(message)s",
    )

    project_root = find_project_root("modules", "tools")
    modules_dir = os.path.join(project_root, "modules")
    registry = discover_modules(modules_dir)

    if args.module not in registry:
        # Fuzzy match
        matches = [n for n in registry if args.module.lower() in n.lower()]
        if len(matches) == 1:
            args.module = matches[0]
        elif matches:
            print(f"Ambiguous: {', '.join(matches)}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"Unknown module: {args.module}", file=sys.stderr)
            sys.exit(1)

    info = registry[args.module]
    out_dir = args.output or os.path.join(info["path"], "export")
    os.makedirs(out_dir, exist_ok=True)

    all_paths = list(dict.fromkeys(resolve_deps(args.module, registry) + [info["verilog"]]))
    top_name = args.module.replace("-", "_")

    fmt = args.format

    # --- CircuitVerse via Yosys (flattened) ---
    if fmt == "circuitverse-yosys":
        cv, netlist = generate_circuitverse_yosys(all_paths, top_name, gate_level=args.gate, check=args.check)
        suffix = "gate" if args.gate else "hlsynth"

    # --- CircuitVerse via Yosys (hierarchical) ---
    elif fmt == "circuitverse-yosys-hier":
        cache_subdir = ".scope_cache_gate" if args.gate else ".scope_cache"
        cache_dir = os.path.join(_SCRIPT_DIR, cache_subdir) if args.cache else None
        cv, netlist = generate_circuitverse_yosys_hier(all_paths, top_name,
                                             cache_dir=cache_dir,
                                             gate_level=args.gate)
        suffix = "gate-hier" if args.gate else "hlsynth-hier"

    # Dump Yosys synthesis JSON
    elab_path = os.path.join(out_dir, f"{args.module}_elaborated.json")
    with open(elab_path, "w") as f:
        json.dump(netlist, f, indent=2)
    print(f"  -> {os.path.relpath(elab_path, project_root)}")

    # Dump CircuitVerse JSON
    cv_path = os.path.join(out_dir, f"{args.module}.{suffix}.cv.json")
    with open(cv_path, "w") as f:
        json.dump(cv, f, indent=2)
    print(f"  -> {os.path.relpath(cv_path, project_root)}")


if __name__ == "__main__":
    main()
