"""Tool helpers: listing, example extraction, interactive tool REPL."""

import os
import re
import shlex
import subprocess
import sys

from manager_utils import (
    Prompt,
    arrow_select,
    extract_summary,
    fallback_select,
)


def list_tools(tools_dir):
    """Return sorted list of (tool_name, script_path, readme_path) from tools/."""
    tools = []
    skip = {"manager", "__pycache__"}
    for entry in sorted(os.listdir(tools_dir)):
        if entry in skip or entry.startswith("."):
            continue
        tool_dir = os.path.join(tools_dir, entry)
        if not os.path.isdir(tool_dir):
            continue
        script = os.path.join(tool_dir, f"{entry}.py")
        readme = os.path.join(tool_dir, "README.md")
        if os.path.isfile(script):
            tools.append((entry, script, readme if os.path.isfile(readme) else None))
    return tools


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


def select_tool(console, tools):
    """Arrow-key selection of a tool, with text fallback."""
    entries = []
    for name, _, readme in tools:
        summary = extract_summary(readme)
        entries.append(f"{name:15s} {summary}" if summary else name)

    idx = arrow_select("Select tool:", entries)
    if idx is not None:
        return tools[idx]

    idx = fallback_select(console, entries, "Select tool")
    return tools[idx]


def interactive_tool(console, name, script, readme, project_root):
    """Show help/examples and prompt the user for arguments, then run."""
    rel_script = os.path.relpath(script, project_root)

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

    examples = extract_examples(readme, name)

    while True:
        used_arrow = False
        if examples:
            menu_entries = examples + ["─ custom args ─", "─ quit ─"]
            idx = arrow_select(f"{name} — select example or custom:", menu_entries)
            if idx is not None:
                used_arrow = True
                if idx == len(menu_entries) - 1:
                    return
                if idx == len(menu_entries) - 2:
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

        try:
            run_args = shlex.split(args_str)
        except ValueError as e:
            console.print(f"[red]Parse error: {e}[/red]")
            continue

        console.print("[dim]─── running ───[/dim]")
        ret = subprocess.call([sys.executable, script] + run_args, cwd=project_root)
        console.print(f"[dim]─── exit {ret} ───[/dim]")
        console.print()
