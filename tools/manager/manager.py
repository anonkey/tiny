#!/usr/bin/env python3
"""Unified manager for packages and tools.

Usage:
    python manage.py                              # interactive (packages / tools)
    python manage.py alu                          # show ALU actions
    python manage.py --run alu                    # run ALU tests
    python manage.py --run alu --fst              # run with FST waveforms
    python manage.py --deps half_cpu              # show dependency tree
    python manage.py --tool assembler -- --help   # run tool directly
    python manage.py --export-all                 # export all modules (circuitverse-yosys --gate)
"""

import os
import subprocess
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from manager_utils import (
    Console,
    arrow_select,
    discover_modules,
    fallback_select,
    find_project_root,
    resolve_name,
)
from manager_modules import (
    interactive_module,
    run_tests,
    select_module,
    show_deps_tree,
)
from manager_tools import (
    interactive_tool,
    list_tools,
    select_tool,
)

PROJECT_ROOT = find_project_root("modules", "tools")
MODULES_DIR = os.path.join(PROJECT_ROOT, "modules")
TOOLS_DIR = os.path.join(PROJECT_ROOT, "tools")
MAKEFILE_SIM = os.path.join(TOOLS_DIR, "Makefile.sim")


def main():
    console = Console()
    registry = discover_modules(MODULES_DIR)
    args = sys.argv[1:]

    # --- CLI flags ---
    if args and args[0] == "--run-all":
        fst = "--fst" in args
        testable = sorted(n for n, info in registry.items() if info.has_test)
        failed = []
        for mod in testable:
            ret = run_tests(console, mod, registry, PROJECT_ROOT, MAKEFILE_SIM, fst=fst)
            if ret != 0:
                failed.append(mod)
        if failed:
            console.print(f"\n[red]Failed: {', '.join(failed)}[/red]")
            sys.exit(1)
        console.print(f"\n[green]All {len(testable)} modules passed[/green]")
        sys.exit(0)

    if args and args[0] == "--run":
        if len(args) < 2:
            print("usage: manage.py --run <module> [--fst]", file=sys.stderr)
            sys.exit(1)
        mod = resolve_name(args[1], list(registry.keys()), key_fn=lambda n: n)
        fst = "--fst" in args
        sys.exit(run_tests(console, mod, registry, PROJECT_ROOT, MAKEFILE_SIM, fst=fst))

    if args and args[0] == "--deps":
        if len(args) < 2:
            print("usage: manage.py --deps <module>", file=sys.stderr)
            sys.exit(1)
        mod = resolve_name(args[1], list(registry.keys()), key_fn=lambda n: n)
        show_deps_tree(console, mod, registry, MODULES_DIR)
        sys.exit(0)

    if args and args[0] == "--export-all":
        export_script = os.path.join(TOOLS_DIR, "verilog_export", "verilog_export.py")
        passthrough = args[1:]  # e.g. --gate
        if not any(a in ("-f", "--format") for a in passthrough):
            passthrough = ["-f", "circuitverse-yosys", "--gate"] + passthrough
        modules = sorted(registry.keys())
        failed = []
        for mod in modules:
            console.print(f"[bold]=== {mod} ===[/bold]")
            ret = subprocess.call(
                [sys.executable, export_script, mod] + passthrough,
                cwd=PROJECT_ROOT,
            )
            if ret != 0:
                failed.append(mod)
        if failed:
            console.print(f"\n[red]Failed: {', '.join(failed)}[/red]")
            sys.exit(1)
        console.print(f"\n[green]All {len(modules)} modules exported[/green]")
        sys.exit(0)

    if args and args[0] == "--tool":
        tools = list_tools(TOOLS_DIR)
        if len(args) < 2:
            print("usage: manage.py --tool <name> [-- args...]", file=sys.stderr)
            sys.exit(1)
        name, script, readme = resolve_name(args[1], tools, key_fn=lambda t: t[0])
        if "--" in args:
            sep = args.index("--")
            passthrough = args[sep + 1:]
            sys.exit(subprocess.call([sys.executable, script] + passthrough, cwd=PROJECT_ROOT))
        interactive_tool(console, name, script, readme, PROJECT_ROOT)
        return

    # --- Positional arg: module name ---
    if args and not args[0].startswith("-"):
        mod = resolve_name(args[0], list(registry.keys()), key_fn=lambda n: n)
        interactive_module(console, mod, registry, MODULES_DIR, PROJECT_ROOT, MAKEFILE_SIM)
        return

    # --- Interactive top-level ---
    top_entries = ["packages", "tools"]
    idx = arrow_select("Select:", top_entries)
    if idx is None:
        idx = fallback_select(console, top_entries, "Select")

    if top_entries[idx] == "packages":
        mod = select_module(console, registry)
        interactive_module(console, mod, registry, MODULES_DIR, PROJECT_ROOT, MAKEFILE_SIM)
    else:
        tools = list_tools(TOOLS_DIR)
        if not tools:
            console.print("[red]No tools found[/red]")
            sys.exit(1)
        name, script, readme = select_tool(console, tools)
        interactive_tool(console, name, script, readme, PROJECT_ROOT)


if __name__ == "__main__":
    main()
