"""Shared type aliases for the verilog_export package."""

from __future__ import annotations

from typing import Any

# A single CircuitVerse node dict (element of na.nodes / allNodes)
NodeDict = dict[str, Any]

# A single CircuitVerse component dict
CompDict = dict[str, Any]

# components dict: objectType -> [component_dict, ...]
CompMap = dict[str, list[CompDict]]

# bit_nodes: Yosys bit ID -> list of allocated node IDs
BitNodes = dict[int, list[int]]

# Yosys JSON module dict (ymod)
YosysModule = dict[str, Any]

# Absolute positions list: index = node ID, value = (x, y)
AbsPos = list[tuple[int, int]]

# CircuitVerse scope dict (top-level JSON structure)
ScopeDict = dict[str, Any]

# Entity key used in splitter_pass producers/consumers
EntityKey = tuple[str, str]

# Producer entry: (entity_key, port_name, port_bits)
ProducerEntry = tuple[EntityKey, str, list[int]]
