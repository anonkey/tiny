"""Netlist transformation pass: insert $cv_splitter cells for width mismatches.

Runs after Yosys synthesis, before placement.  Walks every connection
and inserts explicit splitter cells whenever bits are grouped
differently between producer and consumer.

LEFT splitters (joiners): multiple narrow sources -> one wide consumer.
RIGHT splitters (fan-out): one wide producer -> multiple narrow consumers.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from common.types import YosysModule, YosysCell, ProducerEntry

_log: logging.Logger = logging.getLogger(__name__)
_counter: int = 0


def _fresh_name() -> str:
    global _counter
    name = f"$cv_splitter_{_counter}"
    _counter += 1
    return name


def _max_bit_id(ymod: YosysModule) -> int:
    """Find the highest integer bit ID used in the module."""
    mx = 0
    for port_info in ymod.get("ports", {}).values():
        for b in port_info.get("bits", []):
            if isinstance(b, int) and b > mx:
                mx = b
    for cell in ymod.get("cells", {}).values():
        for bits in cell.get("connections", {}).values():
            for b in bits:
                if isinstance(b, int) and b > mx:
                    mx = b
    return mx


def _build_producers(ymod: YosysModule) -> dict[int, ProducerEntry]:
    """Map each bit ID to its producer (entity_key, port_name, port_bits).

    Module input ports produce bits.  Cell output ports produce bits.
    Returns {bit_id: (entity_key, port_name, port_bits)}.
    entity_key is ("port", name) or ("cell", name).
    """
    producers: dict[int, ProducerEntry] = {}

    # Module input ports are producers
    for pname, pinfo in ymod.get("ports", {}).items():
        if pinfo["direction"] != "input":
            continue
        bits = [b for b in pinfo["bits"] if isinstance(b, int)]
        for b in bits:
            producers[b] = (("port", pname), pname, bits)

    # Cell output ports are producers
    for cname, cell in ymod.get("cells", {}).items():
        dirs = cell.get("port_directions", {})
        conns = cell.get("connections", {})
        for port_name, d in dirs.items():
            if d != "output":
                continue
            bits = [b for b in conns.get(port_name, []) if isinstance(b, int)]
            for b in bits:
                producers[b] = (("cell", cname), port_name, bits)

    return producers


def _build_consumers(ymod: YosysModule) -> dict[int, list[ProducerEntry]]:
    """Map each bit ID to its consumers.

    Cell input ports consume bits.  Module output ports consume bits.
    Returns {bit_id: [(entity_key, port_name, port_bits), ...]}.
    entity_key is ("port", name) or ("cell", name).
    """
    consumers: defaultdict[int, list[ProducerEntry]] = defaultdict(list)

    # Cell input ports are consumers
    for cname, cell in ymod.get("cells", {}).items():
        dirs = cell.get("port_directions", {})
        conns = cell.get("connections", {})
        for port_name, d in dirs.items():
            if d != "input":
                continue
            bits = conns.get(port_name, [])
            for b in bits:
                if isinstance(b, int):
                    consumers[b].append((("cell", cname), port_name, bits))

    # Module output ports are consumers
    for pname, pinfo in ymod.get("ports", {}).items():
        if pinfo["direction"] != "output":
            continue
        bits = pinfo["bits"]
        for b in bits:
            if isinstance(b, int):
                consumers[b].append((("port", pname), pname, bits))

    return consumers


def _compute_groups(
    consumer_bits: list[int | str],
    producers: dict[int, ProducerEntry],
) -> list[tuple[int, list[int | str]]]:
    """Compute split groups for a consumer port based on its producers.

    Walks the consumer's bit array left-to-right, grouping consecutive bits
    that come from the same producer port at contiguous positions.

    Returns list of (group_width, source_bits) tuples.
    """
    groups: list[tuple[int, list[int | str]]] = []
    i = 0
    n = len(consumer_bits)

    while i < n:
        b = consumer_bits[i]
        if not isinstance(b, int):
            groups.append((1, [b]))
            i += 1
            continue

        prod = producers.get(b)
        if prod is None:
            groups.append((1, [b]))
            i += 1
            continue

        entity_key, port_name, prod_bits = prod
        # Find position of b in producer's bit array
        try:
            prod_pos = prod_bits.index(b)
        except ValueError:
            groups.append((1, [b]))
            i += 1
            continue

        # Extend group as long as next consumer bit comes from same producer
        # at contiguous position
        group_len = 1
        while i + group_len < n:
            next_b = consumer_bits[i + group_len]
            if not isinstance(next_b, int):
                _log.debug("  _compute_groups: break at pos %d, not int: %s", i + group_len, next_b)
                break
            next_prod = producers.get(next_b)
            if next_prod is None:
                _log.debug("  _compute_groups: break at pos %d, bit %d has no producer", i + group_len, next_b)
                break
            next_ek, next_pn, next_pb = next_prod
            if next_ek != entity_key or next_pn != port_name:
                _log.debug("  _compute_groups: break at pos %d, bit %d: entity %s.%s != %s.%s",
                           i + group_len, next_b, next_ek, next_pn, entity_key, port_name)
                break
            try:
                next_pos = next_pb.index(next_b)
            except ValueError:
                _log.debug("  _compute_groups: break at pos %d, bit %d not in prod_bits", i + group_len, next_b)
                break
            if next_pos != prod_pos + group_len:
                _log.debug("  _compute_groups: break at pos %d, bit %d: prod_pos %d != expected %d",
                           i + group_len, next_b, next_pos, prod_pos + group_len)
                break
            group_len += 1

        _log.debug("  _compute_groups: group start=%d len=%d bits=%s prod=%s.%s prod_pos=%d",
                   i, group_len, consumer_bits[i:i + group_len], entity_key, port_name, prod_pos)
        groups.append((group_len, consumer_bits[i:i + group_len]))
        i += group_len

    return groups


def _compute_fanout_groups(
    producer_bits: list[int | str],
    consumers: dict[int, list[ProducerEntry]],
) -> list[tuple[int, list[int | str]]]:
    """Compute fan-out groups for a producer port based on its consumers.

    Walks the producer's bit array left-to-right, grouping consecutive bits
    that go to the same consumer port at contiguous positions.

    Returns list of (group_width, source_bits) tuples, or None if no
    fan-out splitting is needed.
    """
    groups: list[tuple[int, list[int | str]]] = []
    i = 0
    n = len(producer_bits)

    while i < n:
        b = producer_bits[i]
        if not isinstance(b, int):
            groups.append((1, [b]))
            i += 1
            continue

        cons_list = consumers.get(b, [])
        if not cons_list:
            groups.append((1, [b]))
            i += 1
            continue

        # Use the first consumer as the grouping key
        entity_key, port_name, cons_bits = cons_list[0]
        try:
            cons_pos = cons_bits.index(b)
        except ValueError:
            groups.append((1, [b]))
            i += 1
            continue

        # Extend group as long as next producer bit goes to same consumer
        # at contiguous position
        group_len = 1
        while i + group_len < n:
            next_b = producer_bits[i + group_len]
            if not isinstance(next_b, int):
                _log.debug("  _compute_fanout: break at pos %d, not int: %s", i + group_len, next_b)
                break
            next_cons_list = consumers.get(next_b, [])
            if not next_cons_list:
                _log.debug("  _compute_fanout: break at pos %d, bit %d has no consumer", i + group_len, next_b)
                break
            next_ek, next_pn, next_cb = next_cons_list[0]
            if next_ek != entity_key or next_pn != port_name:
                _log.debug("  _compute_fanout: break at pos %d, bit %d: entity %s.%s != %s.%s",
                           i + group_len, next_b, next_ek, next_pn, entity_key, port_name)
                break
            try:
                next_pos = next_cb.index(next_b)
            except ValueError:
                _log.debug("  _compute_fanout: break at pos %d, bit %d not in cons_bits", i + group_len, next_b)
                break
            if next_pos != cons_pos + group_len:
                _log.debug("  _compute_fanout: break at pos %d, bit %d: cons_pos %d != expected %d",
                           i + group_len, next_b, next_pos, cons_pos + group_len)
                break
            group_len += 1

        _log.debug("  _compute_fanout: group start=%d len=%d bits=%s cons=%s.%s cons_pos=%d",
                   i, group_len, producer_bits[i:i + group_len], entity_key, port_name, cons_pos)
        groups.append((group_len, producer_bits[i:i + group_len]))
        i += group_len

    return groups


def _needs_splitter(groups: list[tuple[int, list[int | str]]], total_bw: int) -> bool:
    """Return True if a splitter is needed (more than one group or partial)."""
    if len(groups) == 1 and groups[0][0] == total_bw:
        return False
    if len(groups) <= 1:
        return False
    return True


def _insert_left(
    bits: list[int | str],
    groups: list[tuple[int, list[int | str]]],
    new_cells: dict[str, YosysCell],
    producers: dict[int, ProducerEntry],
    next_bit: int,
) -> tuple[str, list[int], int]:
    """Insert a LEFT splitter (joiner): N narrow inputs -> 1 wide output.

    Returns (fresh_bits, next_bit).
    """
    bw = len(bits)
    group_widths = [g[0] for g in groups]

    fresh_bits = list(range(next_bit, next_bit + bw))
    next_bit += bw

    spl_name = _fresh_name()
    port_dirs = {}
    connections = {}
    for idx, (gw, gbits) in enumerate(groups):
        pn = f"I{idx}"
        port_dirs[pn] = "input"
        connections[pn] = list(gbits)

    port_dirs["O"] = "output"
    connections["O"] = fresh_bits

    new_cells[spl_name] = {
        "hide_name": 1,
        "type": "$cv_splitter",
        "parameters": {
            "BW": bw,
            "DIRECTION": "LEFT",
            "GROUPS": group_widths,
        },
        "attributes": {},
        "port_directions": port_dirs,
        "connections": connections,
    }

    for b in fresh_bits:
        producers[b] = (("cell", spl_name), "O", fresh_bits)

    return spl_name, fresh_bits, next_bit


def _insert_right(
    bits: list[int | str],
    groups: list[tuple[int, list[int | str]]],
    new_cells: dict[str, YosysCell],
    producers: dict[int, ProducerEntry],
    next_bit: int,
) -> tuple[str, dict[int, int], int]:
    """Insert a RIGHT splitter (fan-out): 1 wide input -> N narrow outputs.

    Returns (spl_name, output_bit_map, next_bit).
    output_bit_map = {old_bit: new_bit} for rewriting consumers.
    """
    bw = len(bits)
    group_widths = [g[0] for g in groups]

    spl_name = _fresh_name()
    port_dirs = {"I": "input"}
    connections = {"I": list(bits)}

    output_bit_map = {}
    all_fresh = []
    for idx, (gw, gbits) in enumerate(groups):
        pn = f"O{idx}"
        port_dirs[pn] = "output"
        fresh = list(range(next_bit, next_bit + gw))
        next_bit += gw
        connections[pn] = fresh
        all_fresh.extend(fresh)
        for old_b, new_b in zip(gbits, fresh):
            if isinstance(old_b, int):
                output_bit_map[old_b] = new_b

    new_cells[spl_name] = {
        "hide_name": 1,
        "type": "$cv_splitter",
        "parameters": {
            "BW": bw,
            "DIRECTION": "RIGHT",
            "GROUPS": group_widths,
        },
        "attributes": {},
        "port_directions": port_dirs,
        "connections": connections,
    }

    # Update producers: each fresh output bit is now produced by this splitter
    for idx, (_, gbits) in enumerate(groups):
        pn = f"O{idx}"
        fresh = connections[pn]
        for b in fresh:
            producers[b] = (("cell", spl_name), pn, fresh)

    return spl_name, output_bit_map, next_bit


def insert_splitters(ymod: YosysModule) -> YosysModule:
    """Insert $cv_splitter cells into ymod for all width mismatches.

    Single unified pass over every connection:
    1. Consumer-side (LEFT/joiner): cell input ports + module output ports
       whose bits come from multiple distinct producer groups.
    2. Producer-side (RIGHT/fan-out): module input ports + cell output ports
       whose bits fan out to multiple distinct consumer groups.

    Mutates ymod in place.
    """
    global _counter
    _counter = 0

    producers: dict[int, ProducerEntry] = _build_producers(ymod)
    consumers: dict[int, list[ProducerEntry]] = _build_consumers(ymod)
    next_bit: int = _max_bit_id(ymod) + 1
    new_cells: dict[str, YosysCell] = {}

    # Debug: dump producer map for module ports
    for pname, pinfo in ymod.get("ports", {}).items():
        bits = pinfo["bits"]
        _log.debug("PORT %s [%s] bits=%s", pname, pinfo["direction"], bits)
        for b in bits:
            if isinstance(b, int) and b in producers:
                ek, pn, pb = producers[b]
                _log.debug("  bit %d -> producer %s.%s (prod_bits=%s, pos=%s)",
                           b, ek, pn, pb,
                           pb.index(b) if b in pb else "?")
            elif isinstance(b, int):
                _log.debug("  bit %d -> NO PRODUCER", b)

    # ── Consumer-side: LEFT splitters (joiners) ──────────────────────────

    # Cell input ports
    for cname, cell in list(ymod.get("cells", {}).items()):
        if cell.get("type", "").startswith("$cv_splitter"):
            continue
        dirs = cell.get("port_directions", {})
        conns = cell.get("connections", {})

        for port_name, d in dirs.items():
            if d != "input":
                continue
            bits = conns.get(port_name, [])
            int_bits = [b for b in bits if isinstance(b, int)]
            if len(int_bits) <= 1:
                continue

            groups = _compute_groups(bits, producers)
            if not _needs_splitter(groups, len(bits)):
                _log.debug("LEFT skip %s.%s: single group, no mismatch", cname, port_name)
                continue

            spl_name, fresh_bits, next_bit = _insert_left(
                bits, groups, new_cells, producers, next_bit)
            conns[port_name] = fresh_bits

            _log.debug("LEFT %s: %s.%s groups=%s",
                       spl_name, cname, port_name,
                       [g[0] for g in groups])

    # Module output ports
    for pname, pinfo in ymod.get("ports", {}).items():
        if pinfo["direction"] != "output":
            continue
        bits = pinfo["bits"]
        int_bits = [b for b in bits if isinstance(b, int)]
        if len(int_bits) <= 1:
            continue

        groups = _compute_groups(bits, producers)
        _log.debug("LEFT port %s: bits=%s groups=%s total_bw=%d",
                   pname, bits, [(gw, gb) for gw, gb in groups], len(bits))
        if not _needs_splitter(groups, len(bits)):
            _log.debug("LEFT skip port %s: single group, no mismatch", pname)
            continue

        spl_name, fresh_bits, next_bit = _insert_left(
            bits, groups, new_cells, producers, next_bit)
        pinfo["bits"] = fresh_bits

        _log.debug("LEFT %s: port %s groups=%s",
                   spl_name, pname, [g[0] for g in groups])

    # ── Producer-side: RIGHT splitters (fan-out) ─────────────────────────

    # Flush LEFT splitters into ymod so _build_consumers sees their input ports
    if new_cells:
        ymod.setdefault("cells", {}).update(new_cells)
        new_cells = {}

    # Rebuild consumers after LEFT splitter rewrites may have changed connections
    consumers = _build_consumers(ymod)

    # Collect all producer ports: (entity_label, bits)
    producer_ports: list[tuple[str, list[int]]] = []

    for pname, pinfo in ymod.get("ports", {}).items():
        if pinfo["direction"] != "input":
            continue
        bits = [b for b in pinfo["bits"] if isinstance(b, int)]
        if len(bits) > 1:
            producer_ports.append((f"port:{pname}", bits))

    for cname, cell in list(ymod.get("cells", {}).items()):
        if cell.get("type", "").startswith("$cv_splitter"):
            continue
        dirs = cell.get("port_directions", {})
        conns = cell.get("connections", {})
        for port_name, d in dirs.items():
            if d != "output":
                continue
            bits = [b for b in conns.get(port_name, []) if isinstance(b, int)]
            if len(bits) > 1:
                producer_ports.append((f"cell:{cname}.{port_name}", bits))

    for label, bits in producer_ports:
        groups = _compute_fanout_groups(bits, consumers)
        _log.debug("RIGHT %s: bits=%s groups=%s total_bw=%d",
                   label, bits, [(gw, gb) for gw, gb in groups], len(bits))
        if not _needs_splitter(groups, len(bits)):
            _log.debug("RIGHT skip %s: single group, no mismatch", label)
            continue

        spl_name, output_bit_map, next_bit = _insert_right(
            bits, groups, new_cells, producers, next_bit)

        # Rewrite all consumer connections to use the fresh output bits
        for cname, cell in ymod.get("cells", {}).items():
            if cell.get("type", "").startswith("$cv_splitter"):
                # Don't rewrite splitters we just created
                if cname in new_cells:
                    continue
            conns = cell.get("connections", {})
            dirs = cell.get("port_directions", {})
            for cp_name, cp_dir in dirs.items():
                if cp_dir != "input":
                    continue
                cp_bits = conns.get(cp_name, [])
                changed = False
                new_bits = []
                for b in cp_bits:
                    if isinstance(b, int) and b in output_bit_map:
                        new_bits.append(output_bit_map[b])
                        changed = True
                    else:
                        new_bits.append(b)
                if changed:
                    conns[cp_name] = new_bits

        # Also rewrite module output port connections
        for _, out_pinfo in ymod.get("ports", {}).items():
            if out_pinfo["direction"] != "output":
                continue
            out_bits = out_pinfo["bits"]
            changed = False
            new_bits = []
            for b in out_bits:
                if isinstance(b, int) and b in output_bit_map:
                    new_bits.append(output_bit_map[b])
                    changed = True
                else:
                    new_bits.append(b)
            if changed:
                out_pinfo["bits"] = new_bits

        _log.debug("RIGHT %s: %s groups=%s",
                   spl_name, label, [g[0] for g in groups])

    # Add all new cells
    ymod.setdefault("cells", {}).update(new_cells)

    if new_cells:
        _log.info("inserted %d splitter(s)", len(new_cells))
        for sname, sc in new_cells.items():
            p = sc["parameters"]
            _log.info("  %s: dir=%s bw=%d groups=%s", sname, p["DIRECTION"], p["BW"], p["GROUPS"])
    else:
        _log.debug("no splitters needed")

    return ymod
