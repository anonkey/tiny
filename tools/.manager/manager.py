#!/usr/bin/env python3
"""List and run project tools with interactive parameter input.

Usage:
    python tools/.manager/manager.py              # interactive selection + run
    python tools/.manager/manager.py waveform     # interactive params for waveform
    python tools/.manager/manager.py assembler -- example.asm -o out.hex  # direct run
"""

import os
import re
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
    """Walk up from script location to find the project root (contains src/ and tools/)."""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        if os.path.isdir(os.path.join(d, "src")) and os.path.isdir(os.path.join(d, "tools")):
            return d
        d = os.path.dirname(d)
    return os.getcwd()


PROJECT_ROOT = find_project_root()
TOOLS_DIR = os.path.join(PROJECT_ROOT, "tools")


def list_tools():
    """Return sorted list of (tool_name, script_path, readme_path) from tools/."""
    tools = []
    for entry in sorted(os.listdir(TOOLS_DIR)):
        tool_dir = os.path.join(TOOLS_DIR, entry)
        if not os.path.isdir(tool_dir) or entry.startswith("."):
            continue
        script = os.path.join(tool_dir, f"{entry}.py")
        readme = os.path.join(tool_dir, "README.md")
        if os.path.isfile(script):
            tools.append((entry, script, readme if os.path.isfile(readme) else None))
    return tools


def extract_summary(readme_path):
    """Extract the blockquote summary line from a README."""
    if not readme_path:
        return ""
    with open(readme_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("> "):
                return line.removeprefix("> ").strip("* ")
    return ""


def extract_examples(readme_path, tool_name):
    """Extract example commands from a README's code blocks."""
    if not readme_path:
        return []
    examples = []
    in_code = False
    with open(readme_path) as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code = not in_code
                continue
            if in_code and tool_name in stripped and not stripped.startswith("#"):
                # Extract just the arguments after the script name
                match = re.search(rf'{tool_name}\.py\s+(.*)', stripped)
                if match:
                    examples.append(match.group(1))
    return examples


def get_help_output(script):
    """Run the tool with --help and return the output."""
    try:
        result = subprocess.run(
            [sys.executable, script, "--help"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, OSError):
        return ""


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


def interactive_select(console, tools):
    """Arrow-key selection of a tool, with text fallback."""
    entries = []
    for name, _, readme in tools:
        summary = extract_summary(readme)
        entries.append(f"{name:15s} {summary}" if summary else name)

    idx = arrow_select("Select tool:", entries)
    if idx is not None:
        return tools[idx]

    # Fallback: numbered list
    for i, entry in enumerate(entries, 1):
        print(f"  {i}) {entry}")
    while True:
        choice = Prompt.ask("\n[bold]Select tool[/bold]", default="1", console=console)
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(tools):
                return tools[idx]
        except ValueError:
            pass
        matches = [(n, s, r) for n, s, r in tools if choice.lower() in n.lower()]
        if len(matches) == 1:
            return matches[0]
        console.print(f"[red]No match for '{choice}'[/red]")


def interactive_params(console, name, script, readme):
    """Show help/examples and prompt the user for arguments, then run."""
    rel_script = os.path.relpath(script, PROJECT_ROOT)

    # Show usage from --help
    help_text = get_help_output(script)
    if help_text:
        usage_lines = []
        for line in help_text.splitlines():
            if line.startswith("usage:"):
                usage_lines.append(line)
            elif usage_lines and line.startswith(" "):
                usage_lines.append(line)
            elif usage_lines:
                break
        if usage_lines:
            console.print(f"[bold]{name}[/bold]")
            console.print(f"[dim]{chr(10).join(usage_lines)}[/dim]")
            console.print()

    # Show examples from README
    examples = extract_examples(readme, name)

    # Prompt loop
    while True:
        # Offer example selection via arrow keys or custom input
        used_arrow = False
        if examples:
            entries = examples + ["─ custom args ─", "─ quit ─"]
            idx = arrow_select(f"{name} — select example or custom:", entries)
            if idx is not None:
                used_arrow = True
                if idx == len(entries) - 1:
                    return
                if idx == len(entries) - 2:
                    args_str = Prompt.ask("[bold]args[/bold]", console=console).strip()
                else:
                    args_str = examples[idx]
                    console.print(f"[dim]→ python {rel_script} {args_str}[/dim]")
        if not used_arrow:
            if examples:
                for i, ex in enumerate(examples, 1):
                    console.print(f"  [cyan]{i})[/cyan] [dim]{ex}[/dim]")
                console.print()
            try:
                user_input = Prompt.ask(
                    f"[bold]args[/bold] [dim](number for example, or type args, q to quit)[/dim]",
                    console=console,
                )
            except (EOFError, KeyboardInterrupt):
                console.print()
                return
            if user_input.strip().lower() in ("q", "quit", "exit"):
                return
            try:
                idx = int(user_input.strip()) - 1
                if 0 <= idx < len(examples):
                    args_str = examples[idx]
                    console.print(f"[dim]→ python {rel_script} {args_str}[/dim]")
                else:
                    console.print(f"[red]Enter 1-{len(examples)} or type arguments[/red]")
                    continue
            except ValueError:
                args_str = user_input.strip()

        if not args_str:
            continue

        # Parse and run
        try:
            args = shlex.split(args_str)
        except ValueError as e:
            console.print(f"[red]Parse error: {e}[/red]")
            continue

        console.print(f"[dim]─── running ───[/dim]")
        ret = subprocess.call([sys.executable, script] + args, cwd=PROJECT_ROOT)
        console.print(f"[dim]─── exit {ret} ───[/dim]")
        console.print()


def resolve_tool(name, tools):
    """Resolve a tool name argument to (name, script, readme)."""
    tool_map = {n: (n, s, r) for n, s, r in tools}
    if name in tool_map:
        return tool_map[name]
    matches = [(n, s, r) for n, s, r in tools if name.lower() in n.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"'{name}' is ambiguous: {', '.join(n for n, _, _ in matches)}", file=sys.stderr)
        sys.exit(1)
    print(f"No tool matching '{name}'", file=sys.stderr)
    sys.exit(1)


def main():
    console = Console()
    tools = list_tools()

    if not tools:
        console.print("[red]No tools found in tools/[/red]")
        sys.exit(1)

    args = sys.argv[1:]

    # No args → interactive select then interactive params
    if not args:
        name, script, readme = interactive_select(console, tools)
        interactive_params(console, name, script, readme)
        return

    tool_name = args[0]
    name, script, readme = resolve_tool(tool_name, tools)

    # If -- present, run directly with passthrough args
    if "--" in args:
        sep = args.index("--")
        passthrough = args[sep + 1:]
        sys.exit(subprocess.call([sys.executable, script] + passthrough, cwd=PROJECT_ROOT))

    # Otherwise interactive params for the selected tool
    interactive_params(console, name, script, readme)


if __name__ == "__main__":
    main()
