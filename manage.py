#!/usr/bin/env python3
"""Root manager — discovers and runs .manager/manager.py in level-1 subfolders.

Usage:
    python manage.py                    # interactive: pick a folder's manager
    python manage.py test               # run test/.manager/manager.py interactively
    python manage.py test -- alu        # run test/.manager/manager.py with args: alu
    python manage.py test -- cpu pc     # pass multiple args after --
"""

import os
import subprocess
import sys

try:
    from rich.console import Console
    from rich.prompt import Prompt
except ImportError:
    print("error: rich not installed. Run: pip install rich", file=sys.stderr)
    sys.exit(1)

try:
    from simple_term_menu import TerminalMenu
    HAS_MENU = True
except ImportError:
    HAS_MENU = False

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def discover_managers():
    """Find all level-1 subfolders that have a .manager/manager.py."""
    managers = []
    for entry in sorted(os.listdir(PROJECT_ROOT)):
        path = os.path.join(PROJECT_ROOT, entry)
        if not os.path.isdir(path) or entry.startswith("."):
            continue
        manager_py = os.path.join(path, ".manager", "manager.py")
        if os.path.isfile(manager_py):
            managers.append((entry, manager_py))
    return managers


def read_description(manager_py):
    """Extract the first docstring line from a manager script."""
    with open(manager_py) as f:
        in_docstring = False
        for line in f:
            stripped = line.strip()
            if not in_docstring and stripped.startswith('"""'):
                text = stripped.removeprefix('"""')
                if text.endswith('"""'):
                    return text.removesuffix('"""')
                return text if text else ""
            if in_docstring:
                if stripped.endswith('"""'):
                    return ""
                return stripped
    return ""


def interactive_select(console, managers):
    """Arrow-key selection of a manager, with text fallback."""
    entries = []
    for name, path in managers:
        desc = read_description(path)
        entries.append(f"{name:15s} {desc}" if desc else name)

    if HAS_MENU:
        try:
            menu = TerminalMenu(
                entries,
                title="Select manager:",
                cursor_index=0,
                menu_cursor_style=("fg_cyan", "bold"),
                menu_highlight_style=("fg_cyan", "bold"),
            )
            idx = menu.show()
            if idx is None:
                sys.exit(0)
            return managers[idx]
        except (NotImplementedError, OSError):
            pass  # fall through to text fallback

    # Fallback: numbered list
    for i, entry in enumerate(entries, 1):
        print(f"  {i}) {entry}")
    while True:
        choice = Prompt.ask("\n[bold]Select manager[/bold]", default="1", console=console)
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(managers):
                return managers[idx]
        except ValueError:
            pass
        matches = [(n, p) for n, p in managers if choice.lower() in n.lower()]
        if len(matches) == 1:
            return matches[0]
        console.print(f"[red]No match for '{choice}'[/red]")


def main():
    console = Console()
    managers = discover_managers()

    if not managers:
        console.print("[red]No .manager/manager.py found in any subfolder[/red]")
        sys.exit(1)

    args = sys.argv[1:]

    if not args:
        name, manager_py = interactive_select(console, managers)
        passthrough = []
    else:
        folder_name = args[0]
        matches = [(n, p) for n, p in managers if folder_name.lower() in n.lower()]

        if not matches:
            console.print(f"[red]No manager found for '{folder_name}'[/red]")
            sys.exit(1)
        if len(matches) > 1:
            exact = [(n, p) for n, p in matches if n == folder_name]
            if len(exact) == 1:
                matches = exact
            else:
                console.print(f"[yellow]Ambiguous: {', '.join(n for n, _ in matches)}[/yellow]")
                sys.exit(1)

        name, manager_py = matches[0]

        # Args after -- are passed to the sub-manager
        if "--" in args:
            sep = args.index("--")
            passthrough = args[sep + 1:]
        else:
            passthrough = []

    sys.exit(subprocess.call([sys.executable, manager_py] + passthrough))


if __name__ == "__main__":
    main()
