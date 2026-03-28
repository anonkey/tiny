"""Yosys subprocess interface — run synthesis scripts and parse JSON output."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import Any


def run_yosys(script: str) -> dict[str, Any]:
    """Run a Yosys script, return parsed JSON output.

    Raises RuntimeError if Yosys exits with a non-zero status.
    """
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        cmd = ["yosys", "-p", script.format(out=tmp_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Yosys failed:\n{result.stderr}")
        with open(tmp_path) as f:
            return json.load(f)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def yosys_script(verilog_paths: list[str], top_name: str, gate_level: bool = False, flatten: bool = True) -> str:
    """Build a Yosys synthesis script string."""
    read_cmds = "; ".join(f"read_verilog {p}" for p in verilog_paths)
    if gate_level:
        synth_steps = (
            "techmap; opt; "
            "abc -g AND,NAND,OR,NOR,XOR,XNOR,MUX; opt; "
        )
    else:
        synth_steps = "memory -nomap; pmuxtree; opt; "
    flatten_cmd = "flatten; opt; " if flatten else ""
    return (
        f"{read_cmds}; "
        f"hierarchy -top {top_name}; "
        f"proc; opt; {flatten_cmd}"
        f"{synth_steps}"
        f"clean -purge; "
        f"write_json {{out}}"
    )


def check_module_exists(netlist: dict[str, Any], top_name: str) -> None:
    """Raise RuntimeError if top_name is not in the netlist modules."""
    if top_name not in netlist.get("modules", {}):
        avail: list[str] = list(netlist.get("modules", {}).keys())
        raise RuntimeError(
            f"Module '{top_name}' not in Yosys output. Available: {avail}")
