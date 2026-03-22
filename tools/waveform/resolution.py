"""Project root detection and module name resolution."""

import glob
import os
import sys


def find_project_root():
    """Walk up from script location to find the project root (contains modules/ and tools/)."""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        if os.path.isdir(os.path.join(d, "modules")) and os.path.isdir(os.path.join(d, "tools")):
            return d
        d = os.path.dirname(d)
    return os.getcwd()


PROJECT_ROOT = find_project_root()
ARTIFACTS_DIR = os.path.join(PROJECT_ROOT, "artifacts")


def list_available_modules():
    """Scan test/artifacts/ for tb_*.fst files and return module names."""
    modules = {}
    # Search test/artifacts/*/ for FST files (new layout: test/artifacts/<module>/...)
    patterns = [
        os.path.join(ARTIFACTS_DIR, "*", "tb_*.fst"),
        os.path.join(ARTIFACTS_DIR, "tb_*.fst"),
        os.path.join(ARTIFACTS_DIR, "*", "*.fst"),
    ]
    for pat in patterns:
        for fst in sorted(glob.glob(pat)):
            basename = os.path.basename(fst)
            module = basename.removeprefix("tb_").removesuffix(".fst")
            if module not in modules:
                modules[module] = fst
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
        print(f"\u2192 {name} ({os.path.relpath(path, PROJECT_ROOT)})", file=sys.stderr)
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
        print(f"No FST files found in {ARTIFACTS_DIR}", file=sys.stderr)
    sys.exit(1)
