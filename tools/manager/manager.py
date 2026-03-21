#!/usr/bin/env python3
"""Unified manager for packages and tools.

Usage:
    python manage.py                              # interactive (packages / tools)
    python manage.py alu                          # show ALU actions
    python manage.py --run alu                    # run ALU tests
    python manage.py --run alu --fst              # run with FST waveforms
    python manage.py --deps half_cpu              # show dependency tree
    python manage.py --tool assembler -- --help   # run tool directly
"""

import os
import re
import shlex
import subprocess
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from manager_utils import (
    Console,
    Markdown,
    Prompt,
    arrow_select,
    discover_modules,
    extract_summary,
    fallback_select,
    find_project_root,
    resolve_deps,
    resolve_name,
)

PROJECT_ROOT = find_project_root("modules", "tools")
MODULES_DIR = os.path.join(PROJECT_ROOT, "modules")
TOOLS_DIR = os.path.join(PROJECT_ROOT, "tools")
MAKEFILE_SIM = os.path.join(TOOLS_DIR, "Makefile.sim")


# ── Package helpers ──────────────────────────────────────────────────────────

def show_deps_tree(console, name, registry, indent=0):
    """Print a dependency tree recursively."""
    prefix = "  " * indent + ("├─ " if indent else "")
    info = registry[name]
    rel = os.path.relpath(info["path"], MODULES_DIR)
    console.print(f"{prefix}[bold]{name}[/bold] [dim]({rel})[/dim]")
    for dep in info["deps"]:
        show_deps_tree(console, dep, registry, indent + 1)


def make_env():
    """Build environment with venv and homebrew on PATH."""
    venv_bin = os.path.join(PROJECT_ROOT, ".venv", "bin")
    env = os.environ.copy()
    env["PATH"] = f"{venv_bin}:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"
    return env


def run_tests(console, name, registry, fst=False):
    """Run tests for a module via the shared Makefile."""
    info = registry[name]
    if not info["has_test"]:
        console.print(f"[red]No tests for '{name}'[/red]")
        return 1

    # Test files use underscores (e.g. tb_kogge_stone.v for module kogge-stone)
    test_name = name.replace("-", "_")

    sources = resolve_deps(name, registry)
    tb_file = os.path.join(info["path"], "test", f"tb_{test_name}.v")
    sources.append(tb_file)

    test_dir = os.path.join(info["path"], "test")
    cmd = [
        "/usr/bin/make",
        f"-f{MAKEFILE_SIM}",
        f"MOD_NAME={test_name}",
        f"PROJECT_ROOT={PROJECT_ROOT}",
        f"VERILOG_SOURCES={' '.join(sources)}",
    ]
    if fst:
        cmd.append("FST=-fst")

    console.print(f"\n[bold]Running tests for {name}...[/bold]")
    console.print(f"[dim]─── {' '.join(cmd[:4])} ... ───[/dim]")
    ret = subprocess.call(cmd, cwd=test_dir, env=make_env())
    console.print(f"[dim]─── exit {ret} ───[/dim]")
    return ret


def interactive_module(console, name, registry):
    """Show actions for a module: deps, tests, doc."""
    info = registry[name]

    actions = []
    if info["doc"]:
        actions.append("Show doc")
    actions.append("Show deps")
    if info["has_test"]:
        actions.extend(["Run tests", "Run tests (FST)"])
    actions.append("Back")

    while True:
        idx = arrow_select(f"{name}:", actions)
        if idx is not None:
            action = actions[idx]
        else:
            try:
                choice = Prompt.ask(
                    f"[bold]{name}[/bold] [dim]({'|'.join(a[0].lower() for a in actions)})[/dim]",
                    default="b",
                    console=console,
                )
            except (EOFError, KeyboardInterrupt):
                console.print()
                return
            choice = choice.strip().lower()
            action_map = {a[0].lower(): a for a in actions}
            action = action_map.get(choice, "Back")

        if action == "Back":
            return
        elif action == "Show doc":
            with open(info["doc"]) as f:
                console.print(Markdown(f.read()))
        elif action == "Show deps":
            show_deps_tree(console, name, registry)
        elif action == "Run tests":
            run_tests(console, name, registry)
        elif action == "Run tests (FST)":
            run_tests(console, name, registry, fst=True)
        console.print()


def select_module(console, registry):
    """Arrow-key selection of a module, with text fallback."""
    modules = sorted(registry.keys())
    entries = []
    for name in modules:
        info = registry[name]
        test_mark = "✓" if info["has_test"] else " "
        summary = extract_summary(info["doc"]) if info["doc"] else ""
        entries.append(f"[{test_mark}] {name:20s} {summary}")

    idx = arrow_select("Select module:", entries)
    if idx is not None:
        return modules[idx]

    idx = fallback_select(console, entries, "Select module")
    return modules[idx]


# ── Tool helpers ─────────────────────────────────────────────────────────────

def list_tools():
    """Return sorted list of (tool_name, script_path, readme_path) from tools/."""
    tools = []
    skip = {"manager", "__pycache__"}
    for entry in sorted(os.listdir(TOOLS_DIR)):
        if entry in skip or entry.startswith("."):
            continue
        tool_dir = os.path.join(TOOLS_DIR, entry)
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


def interactive_tool(console, name, script, readme):
    """Show help/examples and prompt the user for arguments, then run."""
    rel_script = os.path.relpath(script, PROJECT_ROOT)

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
        ret = subprocess.call([sys.executable, script] + run_args, cwd=PROJECT_ROOT)
        console.print(f"[dim]─── exit {ret} ───[/dim]")
        console.print()


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    console = Console()
    registry = discover_modules(MODULES_DIR)
    args = sys.argv[1:]

    # --- CLI flags ---
    if args and args[0] == "--run-all":
        fst = "--fst" in args
        testable = sorted(n for n, info in registry.items() if info["has_test"])
        failed = []
        for mod in testable:
            ret = run_tests(console, mod, registry, fst=fst)
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
        sys.exit(run_tests(console, mod, registry, fst=fst))

    if args and args[0] == "--deps":
        if len(args) < 2:
            print("usage: manage.py --deps <module>", file=sys.stderr)
            sys.exit(1)
        mod = resolve_name(args[1], list(registry.keys()), key_fn=lambda n: n)
        show_deps_tree(console, mod, registry)
        sys.exit(0)

    if args and args[0] == "--tool":
        tools = list_tools()
        if len(args) < 2:
            print("usage: manage.py --tool <name> [-- args...]", file=sys.stderr)
            sys.exit(1)
        name, script, readme = resolve_name(args[1], tools, key_fn=lambda t: t[0])
        if "--" in args:
            sep = args.index("--")
            passthrough = args[sep + 1:]
            sys.exit(subprocess.call([sys.executable, script] + passthrough, cwd=PROJECT_ROOT))
        interactive_tool(console, name, script, readme)
        return

    # --- Positional arg: module name ---
    if args and not args[0].startswith("-"):
        mod = resolve_name(args[0], list(registry.keys()), key_fn=lambda n: n)
        interactive_module(console, mod, registry)
        return

    # --- Interactive top-level ---
    top_entries = ["packages", "tools"]
    idx = arrow_select("Select:", top_entries)
    if idx is None:
        idx = fallback_select(console, top_entries, "Select")

    if top_entries[idx] == "packages":
        mod = select_module(console, registry)
        interactive_module(console, mod, registry)
    else:
        tools = list_tools()
        if not tools:
            console.print("[red]No tools found[/red]")
            sys.exit(1)
        name, script, readme = select_tool(console, tools)
        interactive_tool(console, name, script, readme)


if __name__ == "__main__":
    main()
