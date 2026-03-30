"""Tests for splitter_pass demux Y-split logic."""

from __future__ import annotations

import sys
import os

# Allow imports from the verilog_export package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synthesis.splitter_pass import _build_producers, insert_splitters


def _make_demux_mux_cell(y_bits: list[int], half: int) -> dict:
    """Build a $mux cell dict that matches the demux pattern."""
    # A inputs: real bits in lower half, const padding in upper half
    a_conn: list[int | str] = list(range(100, 100 + half)) + ["0"] * half
    # B inputs: const padding in lower half, real bits in upper half
    b_conn: list[int | str] = ["0"] * half + list(range(100, 100 + half))
    return {
        "type": "$mux",
        "parameters": {"WIDTH": len(y_bits)},
        "port_directions": {"A": "input", "B": "input", "S": "input", "Y": "output"},
        "connections": {
            "A": a_conn,
            "B": b_conn,
            "S": [99],
            "Y": y_bits,
        },
    }


def _make_normal_mux_cell(y_bits: list[int]) -> dict:
    """Build a $mux cell that is NOT a demux (no constant padding)."""
    n = len(y_bits)
    return {
        "type": "$mux",
        "parameters": {"WIDTH": n},
        "port_directions": {"A": "input", "B": "input", "S": "input", "Y": "output"},
        "connections": {
            "A": list(range(200, 200 + n)),
            "B": list(range(300, 300 + n)),
            "S": [99],
            "Y": y_bits,
        },
    }


def test_build_producers_demux_splits_y():
    """_build_producers should split a demux $mux Y into Y_lo and Y_hi."""
    ymod = {
        "ports": {},
        "cells": {
            "demux_cell": _make_demux_mux_cell([5, 6, 7, 8], half=2),
        },
    }
    producers = _build_producers(ymod)
    # Lower half
    assert producers[5][1] == "Y_lo"
    assert producers[5][2] == [5, 6]
    assert producers[6][1] == "Y_lo"
    assert producers[6][2] == [5, 6]
    # Upper half
    assert producers[7][1] == "Y_hi"
    assert producers[7][2] == [7, 8]
    assert producers[8][1] == "Y_hi"
    assert producers[8][2] == [7, 8]


def test_build_producers_normal_mux_unsplit():
    """_build_producers should NOT split a normal mux Y."""
    ymod = {
        "ports": {},
        "cells": {
            "mux_cell": _make_normal_mux_cell([5, 6, 7, 8]),
        },
    }
    producers = _build_producers(ymod)
    for b in [5, 6, 7, 8]:
        assert producers[b][1] == "Y"
        assert producers[b][2] == [5, 6, 7, 8]


def test_insert_splitters_demux_to_output():
    """insert_splitters should insert a LEFT joiner when demux Y feeds an output port."""
    ymod = {
        "ports": {
            "o_out": {"direction": "output", "bits": [5, 6, 7, 8]},
            "i_data": {"direction": "input", "bits": [100, 101]},
            "i_sel": {"direction": "input", "bits": [99]},
        },
        "cells": {
            "demux_cell": _make_demux_mux_cell([5, 6, 7, 8], half=2),
        },
    }
    insert_splitters(ymod)
    splitters = {k: v for k, v in ymod["cells"].items()
                 if v.get("type") == "$cv_splitter"}
    left_joiners = [v for v in splitters.values()
                    if v["parameters"]["DIRECTION"] == "LEFT"
                    and v["parameters"]["GROUPS"] == [2, 2]]
    assert len(left_joiners) == 1, (
        f"Expected 1 LEFT [2,2] joiner, got {len(left_joiners)}: {splitters}"
    )


def test_insert_splitters_normal_mux_no_extra_splitter():
    """insert_splitters should NOT insert a LEFT joiner for a normal mux."""
    ymod = {
        "ports": {
            "o_out": {"direction": "output", "bits": [5, 6, 7, 8]},
        },
        "cells": {
            "mux_cell": _make_normal_mux_cell([5, 6, 7, 8]),
        },
    }
    insert_splitters(ymod)
    splitters = {k: v for k, v in ymod["cells"].items()
                 if v.get("type") == "$cv_splitter"}
    # No [2,2] joiner should be inserted (that's the demux-specific one)
    left_joiners = [v for v in splitters.values()
                    if v["parameters"]["DIRECTION"] == "LEFT"
                    and v["parameters"]["GROUPS"] == [2, 2]]
    assert len(left_joiners) == 0, f"Expected no [2,2] LEFT joiner, got {left_joiners}"


if __name__ == "__main__":
    test_build_producers_demux_splits_y()
    print("PASS: test_build_producers_demux_splits_y")
    test_build_producers_normal_mux_unsplit()
    print("PASS: test_build_producers_normal_mux_unsplit")
    test_insert_splitters_demux_to_output()
    print("PASS: test_insert_splitters_demux_to_output")
    test_insert_splitters_normal_mux_no_extra_splitter()
    print("PASS: test_insert_splitters_normal_mux_no_extra_splitter")
    print("All tests passed.")
