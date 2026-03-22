#!/usr/bin/env python3
"""Export Verilog modules to various schematic formats.

Parses module headers (ports, parameters, submodule instantiations) and
exports to KiCad (.kicad_sch / .kicad_sym) or CircuitVerse JSON.

Usage:
    python verilog_export.py alu                                    # KiCad flat (default)
    python verilog_export.py half_cpu -f kicad-hier                 # KiCad hierarchical
    python verilog_export.py half_cpu -f kicad-sym                  # KiCad symbols only
    python verilog_export.py half_cpu -f circuitverse               # CircuitVerse (block-level)
    python verilog_export.py half_cpu -f circuitverse-yosys         # CircuitVerse (high-level via Yosys, flat)
    python verilog_export.py half_cpu -f circuitverse-yosys --gate  # CircuitVerse (gate-level via Yosys)
    python verilog_export.py mux -f circuitverse-yosys-hier        # CircuitVerse (high-level via Yosys, hierarchical)
    python verilog_export.py half_cpu -o out/                       # custom output directory
"""

import argparse
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_MANAGER_DIR = os.path.join(os.path.dirname(_SCRIPT_DIR), "manager")
if _MANAGER_DIR not in sys.path:
    sys.path.insert(0, _MANAGER_DIR)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from manager_utils import discover_modules, find_project_root, resolve_deps

from verilog_parser import parse_verilog
from kicad_symbol import generate_sym_lib
from kicad_schematic import generate_flat_schematic, generate_hier_schematic
from circuitverse import generate_circuitverse
from circuitverse_yosys import generate_circuitverse_yosys, generate_circuitverse_yosys_hier

_FORMATS = ["kicad-flat", "kicad-hier", "kicad-sym", "circuitverse", "circuitverse-yosys", "circuitverse-yosys-hier"]


def main():
    parser = argparse.ArgumentParser(
        description="Export Verilog modules to schematic formats."
    )
    parser.add_argument("module", help="Module name (resolved via manager.json)")
    parser.add_argument(
        "-f", "--format", default="kicad-flat", choices=_FORMATS,
        help="Output format (default: kicad-flat)",
    )
    parser.add_argument("-o", "--output", default="", help="Output directory (default: module's export/ subdir)")
    parser.add_argument(
        "-g", "--gate", action="store_true",
        help="Force gate-level synthesis (only for circuitverse-yosys)",
    )
    args = parser.parse_args()

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

    lib_prefix = args.module

    # Parse the top module
    top_modules = parse_verilog(info["verilog"])
    top_mod = None
    for m in top_modules:
        if m.name == args.module.replace("-", "_"):
            top_mod = m
            break
    if not top_mod and top_modules:
        top_mod = top_modules[0]
    if not top_mod:
        print(f"Could not parse module from {info['verilog']}", file=sys.stderr)
        sys.exit(1)

    # Parse all dependency modules
    dep_paths = resolve_deps(args.module, registry)
    sub_modules = []
    seen_names = set()
    for vpath in dep_paths:
        if vpath == info["verilog"]:
            continue
        for m in parse_verilog(vpath):
            if m.name not in seen_names:
                seen_names.add(m.name)
                sub_modules.append(m)

    # Also parse the top module file for any helper modules
    for m in top_modules:
        if m.name != top_mod.name and m.name not in seen_names:
            seen_names.add(m.name)
            sub_modules.append(m)

    # Dump intermediary parsed data
    def _mod_to_dict(m):
        return {
            "name": m.name,
            "params": {p.name: p.default for p in m.params} if hasattr(m, "params") else {},
            "ports": [{"name": p.name, "direction": p.direction, "width": p.width} for p in m.ports],
            "instances": [{"module": i.module_name, "name": i.inst_name, "connections": i.connections} for i in m.instances] if hasattr(m, "instances") else [],
        }

    dump = {
        "top": _mod_to_dict(top_mod),
        "sub_modules": [_mod_to_dict(m) for m in sub_modules],
    }
    dump_path = os.path.join(out_dir, f"{args.module}_parsed.json")
    with open(dump_path, "w") as f:
        json.dump(dump, f, indent=2)
    print(f"  -> dumped parsed data to {os.path.relpath(dump_path, project_root)}")

    # Dump Yosys-elaborated (hierarchical, not flattened) JSON
    import subprocess, tempfile
    all_paths = list(dict.fromkeys(resolve_deps(args.module, registry) + [info["verilog"]]))
    read_cmds = "; ".join(f"read_verilog {p}" for p in all_paths)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        script = f"{read_cmds}; hierarchy -top {top_mod.name}; proc; opt; write_json {tmp_path}"
        result = subprocess.run(["yosys", "-p", script], capture_output=True, text=True)
        if result.returncode == 0:
            elab_path = os.path.join(out_dir, f"{args.module}_elaborated.json")
            with open(tmp_path) as f:
                elab = json.load(f)
            with open(elab_path, "w") as f:
                json.dump(elab, f, indent=2)
            print(f"  -> dumped elaborated data to {os.path.relpath(elab_path, project_root)}")
        else:
            print(f"  (yosys elaboration skipped: {result.stderr.splitlines()[-1]})", file=sys.stderr)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    print(f"Parsed {top_mod.name}: {len(top_mod.ports)} ports, {len(top_mod.instances)} instances")
    print(f"Dependencies: {len(sub_modules)} sub-modules")

    fmt = args.format

    # --- CircuitVerse ---
    if fmt == "circuitverse":
        cv = generate_circuitverse(top_mod, sub_modules)
        cv_path = os.path.join(out_dir, f"{args.module}.cv.json")
        with open(cv_path, "w") as f:
            json.dump(cv, f, indent=2)
        print(f"  -> {os.path.relpath(cv_path, project_root)}")
        return

    # --- CircuitVerse via Yosys (flattened) ---
    if fmt == "circuitverse-yosys":
        all_paths = list(dict.fromkeys(resolve_deps(args.module, registry) + [info["verilog"]]))
        cv = generate_circuitverse_yosys(all_paths, top_mod.name, gate_level=args.gate)
        suffix = "gate" if args.gate else "hlsynth"
        cv_path = os.path.join(out_dir, f"{args.module}.{suffix}.cv.json")
        with open(cv_path, "w") as f:
            json.dump(cv, f, indent=2)
        print(f"  -> {os.path.relpath(cv_path, project_root)}")
        return

    # --- CircuitVerse via Yosys (hierarchical) ---
    if fmt == "circuitverse-yosys-hier":
        all_paths = list(dict.fromkeys(resolve_deps(args.module, registry) + [info["verilog"]]))
        cv = generate_circuitverse_yosys_hier(all_paths, top_mod.name)
        cv_path = os.path.join(out_dir, f"{args.module}.hlsynth-hier.cv.json")
        with open(cv_path, "w") as f:
            json.dump(cv, f, indent=2)
        print(f"  -> {os.path.relpath(cv_path, project_root)}")
        return

    # --- KiCad formats ---
    all_mods = sub_modules + [top_mod]
    sym_content = generate_sym_lib(all_mods, lib_prefix)
    sym_path = os.path.join(out_dir, f"{args.module}.kicad_sym")
    with open(sym_path, "w") as f:
        f.write(sym_content)
    print(f"  -> {os.path.relpath(sym_path, project_root)}")

    if fmt == "kicad-sym":
        return

    if fmt == "kicad-hier":
        sheets = generate_hier_schematic(top_mod, sub_modules, registry, lib_prefix)
        for fname, content in sheets.items():
            fpath = os.path.join(out_dir, fname)
            with open(fpath, "w") as f:
                f.write(content)
            print(f"  -> {os.path.relpath(fpath, project_root)}")
    else:
        flat_content = generate_flat_schematic(top_mod, sub_modules, lib_prefix)
        flat_path = os.path.join(out_dir, f"{args.module}_flat.kicad_sch")
        with open(flat_path, "w") as f:
            f.write(flat_content)
        print(f"  -> {os.path.relpath(flat_path, project_root)}")


if __name__ == "__main__":
    main()
