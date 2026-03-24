"""Package (module) helpers: deps tree, test runner, interactive module menu."""

import os
import subprocess

from manager_utils import (
    Console,
    Markdown,
    Prompt,
    arrow_select,
    extract_summary,
    fallback_select,
    resolve_deps,
)


def show_deps_tree(console, name, registry, modules_dir, indent=0):
    """Print a dependency tree recursively."""
    prefix = "  " * indent + ("├─ " if indent else "")
    info = registry[name]
    rel = os.path.relpath(info["path"], modules_dir)
    console.print(f"{prefix}[bold]{name}[/bold] [dim]({rel})[/dim]")
    for dep in info["deps"]:
        show_deps_tree(console, dep, registry, modules_dir, indent + 1)


def make_env(project_root):
    """Build environment with venv and homebrew on PATH."""
    venv_bin = os.path.join(project_root, ".venv", "bin")
    env = os.environ.copy()
    env["PATH"] = f"{venv_bin}:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"
    return env


def run_tests(console, name, registry, project_root, makefile_sim, fst=False):
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
    artifacts_dir = os.path.join(project_root, "artifacts", test_name)
    os.makedirs(artifacts_dir, exist_ok=True)

    cmd = [
        "/usr/bin/make",
        f"-f{makefile_sim}",
        f"MOD_NAME={test_name}",
        f"PROJECT_ROOT={project_root}",
        f"VERILOG_SOURCES={' '.join(sources)}",
    ]
    if fst:
        cmd.append("FST=-fst")

    env = make_env(project_root)
    helpers_dir = os.path.join(project_root, "tools")
    env["PYTHONPATH"] = test_dir + os.pathsep + helpers_dir + os.pathsep + env.get("PYTHONPATH", "")

    console.print(f"\n[bold]Running tests for {name}...[/bold]")
    console.print(f"[dim]─── {' '.join(cmd[:4])} ... ───[/dim]")
    ret = subprocess.call(cmd, cwd=artifacts_dir, env=env)
    console.print(f"[dim]─── exit {ret} ───[/dim]")
    return ret


def interactive_module(console, name, registry, modules_dir, project_root, makefile_sim):
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
            show_deps_tree(console, name, registry, modules_dir)
        elif action == "Run tests":
            run_tests(console, name, registry, project_root, makefile_sim)
        elif action == "Run tests (FST)":
            run_tests(console, name, registry, project_root, makefile_sim, fst=True)
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
