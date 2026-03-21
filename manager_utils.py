"""Shared utilities for manager scripts."""

import os
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


def find_project_root(*markers):
    """Walk up from caller's location to find the project root containing all marker dirs."""
    d = os.path.dirname(os.path.abspath(sys.argv[0]))
    for _ in range(5):
        if all(os.path.isdir(os.path.join(d, m)) for m in markers):
            return d
        d = os.path.dirname(d)
    return os.getcwd()


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


def extract_summary(path):
    """Extract the blockquote summary line from a markdown file."""
    if not path:
        return ""
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("> "):
                return line.removeprefix("> ").strip("* ")
    return ""


def fallback_select(console, entries, prompt_label="Select"):
    """Numbered list selection with substring match fallback. Returns index or None."""
    for i, entry in enumerate(entries, 1):
        print(f"  {i}) {entry}")
    while True:
        choice = Prompt.ask(f"\n[bold]{prompt_label}[/bold]", default="1", console=console)
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(entries):
                return idx
        except ValueError:
            pass
        # Substring match — caller can refine, but we try on the raw entry strings
        matches = [i for i, e in enumerate(entries) if choice.lower() in e.lower()]
        if len(matches) == 1:
            return matches[0]
        console.print(f"[red]No match for '{choice}'[/red]")


def resolve_name(name, items, key_fn):
    """Resolve a name by exact match then substring. Returns item or exits."""
    for item in items:
        if key_fn(item) == name:
            return item
    matches = [item for item in items if name.lower() in key_fn(item).lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"'{name}' is ambiguous: {', '.join(key_fn(m) for m in matches)}", file=sys.stderr)
        sys.exit(1)
    print(f"No match for '{name}'", file=sys.stderr)
    sys.exit(1)
