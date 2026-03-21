#!/usr/bin/env python3
"""Browse module docs and run tests interactively.

Usage:
    python test/.manager/manager.py              # interactive selection
    python test/.manager/manager.py alu          # show ALU docs + option to run
    python test/.manager/manager.py cpu decoder  # show multiple docs
    python test/.manager/manager.py --run alu    # run ALU tests directly
"""

import os
import shlex
import subprocess
import sys

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.prompt import Prompt
    from rich.table import Table
except ImportError:
    print("error: rich not installed. Run: pip install rich", file=sys.stderr)
    sys.exit(1)

try:
    from simple_term_menu import TerminalMenu
    HAS_MENU = True
except ImportError:
    HAS_MENU = False


def find_project_root():
    """Walk up from script location to find the project root (contains src/ and docs/)."""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        if os.path.isdir(os.path.join(d, "src")) and os.path.isdir(os.path.join(d, "docs")):
            return d
        d = os.path.dirname(d)
    return os.getcwd()


PROJECT_ROOT = find_project_root()
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")
TEST_DIR = os.path.join(PROJECT_ROOT, "test")


def list_modules():
    """Return sorted list of (module_name, doc_path, test_dir) from docs/."""
    modules = []
    for f in sorted(os.listdir(DOCS_DIR)):
        if f.endswith(".md"):
            name = f.removesuffix(".md")
            doc_path = os.path.join(DOCS_DIR, f)
            test_path = os.path.join(TEST_DIR, name)
            has_test = os.path.isfile(os.path.join(test_path, "Makefile"))
            modules.append((name, doc_path, test_path if has_test else None))
    return modules


def extract_summary(path):
    """Extract the blockquote summary line from a doc file."""
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("> "):
                return line.removeprefix("> ").strip("* ")
    return ""


def find_testable_modules():
    """Find modules that have test directories with Makefiles but no docs."""
    doc_names = set()
    for f in os.listdir(DOCS_DIR):
        if f.endswith(".md"):
            doc_names.add(f.removesuffix(".md"))

    extra = []
    for entry in sorted(os.listdir(TEST_DIR)):
        test_path = os.path.join(TEST_DIR, entry)
        if entry in doc_names or entry.startswith(".") or entry == "artifacts":
            continue
        if os.path.isfile(os.path.join(test_path, "Makefile")):
            extra.append((entry, None, test_path))
    return extra


def arrow_select(title, entries):
    """Arrow-key menu selection. Returns index or None if cancelled/unavailable."""
    if not HAS_MENU:
        return None
    try:
        menu = TerminalMenu(
            entries,
            title=title,
            cursor_index=0,
            menu_cursor_style=("fg_cyan", "bold"),
            menu_highlight_style=("fg_cyan", "bold"),
        )
        return menu.show()
    except (NotImplementedError, OSError):
        return None


def interactive_select(console, modules):
    """Arrow-key selection of a module, with text fallback."""
    entries = []
    for name, doc_path, test_path in modules:
        test_mark = "✓" if test_path else " "
        summary = extract_summary(doc_path) if doc_path else "no docs"
        entries.append(f"[{test_mark}] {name:15s} {summary}")

    idx = arrow_select("Select module:", entries)
    if idx is not None:
        return [modules[idx]]

    # Fallback: numbered list
    for i, entry in enumerate(entries, 1):
        print(f"  {i}) {entry}")
    while True:
        choice = Prompt.ask("\n[bold]Select module[/bold]", default="1", console=console)
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(modules):
                return [modules[idx]]
        except ValueError:
            pass
        matches = [(n, d, t) for n, d, t in modules if choice.lower() in n.lower()]
        if len(matches) == 1:
            return matches
        console.print(f"[red]No match for '{choice}'[/red]")


def make_env():
    """Build environment with venv and homebrew on PATH."""
    venv_bin = os.path.join(PROJECT_ROOT, ".venv", "bin")
    env = os.environ.copy()
    env["PATH"] = f"{venv_bin}:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"
    return env


def run_tests(console, name, test_path, make_args=""):
    """Run tests for a module via make."""
    console.print(f"\n[bold]Running tests for {name}...[/bold]")
    cmd = ["/usr/bin/make"] + (shlex.split(make_args) if make_args else [])
    console.print(f"[dim]─── {' '.join(cmd)} (test/{name}) ───[/dim]")
    ret = subprocess.call(cmd, cwd=test_path, env=make_env())
    console.print(f"[dim]─── exit {ret} ───[/dim]")
    return ret


def interactive_module(console, name, doc_path, test_path):
    """Show docs then offer to run tests interactively."""
    if doc_path:
        with open(doc_path) as f:
            console.print(Markdown(f.read()))

    if not test_path:
        return

    console.print()

    actions = ["Run tests", "Run with make args", "Back"]

    while True:
        idx = arrow_select(f"{name}:", actions)
        if idx is not None:
            if idx == 2:
                return
            if idx == 0:
                run_tests(console, name, test_path)
            elif idx == 1:
                make_args = Prompt.ask(
                    "[dim]make args (e.g. FST= , WAVES=1)[/dim]",
                    default="",
                    console=console,
                )
                run_tests(console, name, test_path, make_args)
        else:
            try:
                choice = Prompt.ask(
                    f"[bold]{name}[/bold] [dim](r=run tests, m=make args, q=quit)[/dim]",
                    default="q",
                    console=console,
                )
            except (EOFError, KeyboardInterrupt):
                console.print()
                return
            choice = choice.strip().lower()
            if choice in ("q", "quit", "exit"):
                return
            elif choice in ("r", "run"):
                run_tests(console, name, test_path)
            elif choice in ("m", "make"):
                make_args = Prompt.ask(
                    "[dim]make args (e.g. FST= , WAVES=1)[/dim]",
                    default="",
                    console=console,
                )
                run_tests(console, name, test_path, make_args)

        console.print()


def resolve_modules(names, modules):
    """Resolve module name arguments to (name, doc_path, test_path) triples."""
    module_map = {n: (n, d, t) for n, d, t in modules}
    resolved = []
    for name in names:
        if name in module_map:
            resolved.append(module_map[name])
            continue
        matches = [(n, d, t) for n, d, t in modules if name.lower() in n.lower()]
        if len(matches) == 1:
            resolved.append(matches[0])
        elif len(matches) > 1:
            print(f"'{name}' is ambiguous: {', '.join(n for n, _, _ in matches)}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"No module matching '{name}'", file=sys.stderr)
            sys.exit(1)
    return resolved


def main():
    console = Console()
    modules = list_modules()
    modules.extend(find_testable_modules())
    modules.sort(key=lambda m: m[0])

    if not modules:
        console.print("[red]No modules found[/red]")
        sys.exit(1)

    args = sys.argv[1:]

    # --run flag: run tests directly
    if args and args[0] == "--run":
        if len(args) < 2:
            print("usage: manager.py --run <module> [make_args...]", file=sys.stderr)
            sys.exit(1)
        selected = resolve_modules([args[1]], modules)
        name, _, test_path = selected[0]
        if not test_path:
            print(f"No tests for '{name}'", file=sys.stderr)
            sys.exit(1)
        sys.exit(run_tests(console, name, test_path))

    if args:
        selected = resolve_modules(args, modules)
    else:
        selected = interactive_select(console, modules)

    for i, (name, doc_path, test_path) in enumerate(selected):
        if i > 0:
            console.rule()
        interactive_module(console, name, doc_path, test_path)


if __name__ == "__main__":
    main()
