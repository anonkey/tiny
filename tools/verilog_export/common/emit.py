"""Common component emitters for CircuitVerse export."""

from __future__ import annotations

import logging
from typing import Any

from common.types import CompDict, CompMap, BitNodes
from common.node_alloc import _CVNodeAlloc  # noqa: TC001 — used in type annotations

_log: logging.Logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CircuitVerse JSON key — intentionally misspelled to match upstream API.
# Do NOT "fix" the spelling.
# ---------------------------------------------------------------------------
CTOR_PARAMS_KEY: str = "constructorParamaters"


# ---------------------------------------------------------------------------
# Component helpers
# ---------------------------------------------------------------------------

def _append_comp(components: CompMap, cv_type: str, x: int, y: int,
                 ctor_params: list[Any], nodes: dict[str, Any],
                 **kwargs: Any) -> CompDict:
    """Build a component and append it to the components dict. Returns the component."""
    comp: CompDict = CompDict.create(cv_type, x, y, ctor_params, nodes, **kwargs)
    components.setdefault(cv_type, []).append(comp)
    return comp


# ---------------------------------------------------------------------------
# Common component patterns used by high-level cell handlers
# ---------------------------------------------------------------------------

def emit_constant(na: _CVNodeAlloc, bit_nodes: BitNodes, value_str: str,
                  bw: int, x: int, y: int) -> tuple[CompDict, int]:
    """Emit a ConstantVal component.

    value_str: binary string like "00000001" (MSB first, length == bw).
    Returns (component_dict, output_node_id).
    """
    out_node: int = na.alloc(bw * 10, 0, 1, bw)
    comp: CompDict = CompDict.create("ConstantVal", x, y,
        ["RIGHT", bw, value_str], {"output1": out_node},
        propagation_delay=10)
    return comp, out_node


def emit_not_gate(na: _CVNodeAlloc, bit_nodes: BitNodes, bw: int,
                  x: int, y: int) -> tuple[CompDict, int, int]:
    """Emit a NotGate component.

    Returns (component_dict, inp_node_id, out_node_id).
    """
    inp: int = na.alloc(-10, 0, 0, bw)
    out: int = na.alloc(20, 0, 1, bw)
    comp: CompDict = CompDict.create("NotGate", x, y,
        ["RIGHT", bw], {"inp1": inp, "output1": out})
    return comp, inp, out


def emit_zero_extend(na: _CVNodeAlloc, bit_nodes: BitNodes, in_bw: int,
                     out_bw: int, x: int,
                     y: int) -> tuple[list[CompDict], int, int]:
    """Emit a Splitter + ConstantVal(0) to zero-extend a signal.

    Returns (components_list, input_node_id, output_node_id).
    Where input_node_id is the narrow input and output_node_id is the wide output.
    """
    extra: int = out_bw - in_bw
    comps: list[CompDict] = []

    # Splitter: groups = [in_bw, extra], direction LEFT (combining)
    spl_inp: int = na.alloc(20, (1) * 10, 1, out_bw)  # wide output
    spl_out0: int = na.alloc(-10, -10 * 0, 0, in_bw)  # narrow input
    spl_out1: int = na.alloc(-10, -10 * 0 + 20, 0, extra)  # zero padding
    comps.append(CompDict.create("Splitter", x, y,
        ["LEFT", out_bw, [in_bw, extra]],
        {"outputs": [spl_out0, spl_out1], "inp1": spl_inp},
        direction="LEFT", propagation_delay=10))

    # ConstantVal: all zeros for the extra bits
    zero_str: str = "0" * extra
    zero_comp: CompDict
    zero_out: int
    zero_comp, zero_out = emit_constant(na, bit_nodes, zero_str, extra, x - 60, y + 20)
    comps.append(zero_comp)
    na.connect(zero_out, spl_out1)

    return comps, spl_out0, spl_inp


def register_bits(na: _CVNodeAlloc, bit_nodes: BitNodes,
                  bits: list[int | str], node_id: int, bw: int) -> None:
    """Register a multi-bit node on all its Yosys bit indices.

    For a multi-bit node, each bit index in the Yosys bits array maps to the
    same node_id. This only works when all bits belong to the same bus.
    """
    for b in bits:
        if not isinstance(b, str):
            bit_nodes.setdefault(b, []).append(node_id)


def unique_pos(x: int, y: int, used: set[tuple[int, int]],
               step: int = 20) -> tuple[int, int]:
    """Nudge y until (x, y) is not in the used set, then register it."""
    while (x, y) in used:
        y += step
    used.add((x, y))
    return x, y


def emit_splitter(na: _CVNodeAlloc, bw: int, groups: list[int],
                  direction: str, x: int, y: int,
                  inp_node: int | None = None,
                  out_nodes: list[int] | None = None,
                  ) -> tuple[CompDict, int, list[int]]:
    """Emit a Splitter component.

    direction: "RIGHT" (fan-out / split) or "LEFT" (fan-in / join).
    groups: list of bit widths per output (e.g. [1, 1, 1] or [4, 2]).

    Returns (component_dict, inp_node, output_nodes_list).
    If inp_node/out_nodes are None, allocates with standard positions.
    """
    n: int = len(groups)
    y_offset: int = int((n / 2 - 1) * 20)
    if direction == "RIGHT":
        if inp_node is None:
            inp_node = na.alloc(-10, (bw - 1) * 10, 0, bw)
        if out_nodes is None:
            out_nodes = []
            for i, g in enumerate(groups):
                out_nodes.append(na.alloc(20, i * 20 - y_offset - 20, 1, g))
    else:
        # LEFT: x is mirrored by set_parent_pos, so multi-pin side uses
        # rx=20 (mirrors to left) and bus side uses rx=-10 (mirrors to right).
        if out_nodes is None:
            out_nodes = []
            for i, g in enumerate(groups):
                out_nodes.append(na.alloc(20, i * 20 - y_offset - 20, 0, g))
        if inp_node is None:
            inp_node = na.alloc(-10, 10 + y_offset, 1, bw)

    comp: CompDict = CompDict.create("Splitter", x, y,
        [direction, bw, groups],
        {"outputs": out_nodes, "inp1": inp_node},
        direction=direction, propagation_delay=10)
    return comp, inp_node, out_nodes


def emit_split_reduce(na: _CVNodeAlloc, bit_nodes: BitNodes,
                      components: CompMap, bw: int, inp_node: int,
                      gate_type: str, spl_x: int, spl_y: int,
                      gate_x: int, gate_y: int) -> int:
    """Split a multi-bit signal to 1-bit lines and reduce through an N-input gate.

    inp_node: the multi-bit source node (already allocated, already connected).
    gate_type: "AndGate", "OrGate", "NorGate", "XorGate", "XnorGate", "NandGate".

    Emits a Splitter + gate, appends both to components.
    Returns the 1-bit output node ID.
    """
    spl_comp: CompDict
    spl_inp: int
    spl_outputs: list[int]
    spl_comp, spl_inp, spl_outputs = emit_splitter(
        na, bw, [1] * bw, "RIGHT", spl_x, spl_y)
    na.connect(inp_node, spl_inp)
    components.setdefault("Splitter", []).append(spl_comp)

    from synthesis.gates.registry import pin_pos, gate_output_pos
    gate_inputs: list[int] = []
    for i, spl_out in enumerate(spl_outputs):
        ix, iy = pin_pos(gate_type, "inp", index=i, inputLength=bw)
        gate_inp: int = na.alloc(ix, iy, 0, 1)
        na.connect(spl_out, gate_inp)
        gate_inputs.append(gate_inp)
    ox, oy = gate_output_pos(gate_type)
    gate_out: int = na.alloc(ox, oy, 1, 1)

    _append_comp(components, gate_type, gate_x, gate_y,
        ["RIGHT", bw, 1],
        {"inp": gate_inputs, "output1": gate_out})
    return gate_out


def emit_alu(na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap,
             op_bw: int, ctrl_value: str,
             x: int, y: int, a_node: int, b_node: int) -> tuple[int, int]:
    """Emit an ALU component with a constant control signal.

    ctrl_value: binary string (e.g. "110" for subtraction, "111" for LESS).
    Returns (output_node, carry_out_node).
    """
    from synthesis.gates.registry import pin_pos

    ctrl_comp: CompDict
    ctrl_out: int
    ctrl_comp, ctrl_out = emit_constant(na, bit_nodes, ctrl_value, 3,
                                         x - 60, y - 50)
    components.setdefault("ConstantVal", []).append(ctrl_comp)

    c_x, c_y = pin_pos("ALU", "controlSignalInput")
    o_x, o_y = pin_pos("ALU", "output")
    co_x, co_y = pin_pos("ALU", "carryOut")
    ctrl_in: int = na.alloc(c_x, c_y, 0, 3)
    na.connect(ctrl_out, ctrl_in)
    out_node: int = na.alloc(o_x, o_y, 1, op_bw)
    carry_out: int = na.alloc(co_x, co_y, 1, 1)

    _append_comp(components, "ALU", x, y,
        ["RIGHT", op_bw],
        {"inp1": a_node, "inp2": b_node, "controlSignalInput": ctrl_in,
         "output": out_node, "carryOut": carry_out})
    return out_node, carry_out


def emit_component(na: _CVNodeAlloc, component_type: str, x: int, y: int,
                   direction: str = "RIGHT", label: str = "",
                   propagation_delay: int = 100, bitWidth: int = 1,
                   **extra_params: Any) -> tuple[CompDict, dict[str, int]]:
    """Emit any simple component using the registry for pin positions.

    Handles components with static pins (fixed x/y in the reference).
    For components with dynamic/array pins (gates, mux), use specialized
    emitters or manual allocation.

    Returns (component_dict, {pin_name: node_id}).
    """
    from synthesis.gates.registry import _COMPONENTS, _resolve_bw, pin_pos

    comp_ref: dict[str, Any] | None = _COMPONENTS.get(component_type)
    if comp_ref is None:
        raise KeyError(f"Unknown component: {component_type}")

    params: dict[str, Any] = {"bitWidth": bitWidth, **extra_params}
    pin_nodes: dict[str, int] = {}
    nodes_dict: dict[str, int] = {}

    for pname, pinfo in comp_ref.get("pins", {}).items():
        # Skip array pins — caller must handle these
        if "count" in pinfo or "positions_formula" in pinfo:
            continue
        try:
            px, py = pin_pos(component_type, pname, **params)
        except KeyError:
            _log.debug("skipping unknown pin '%s' on '%s'", pname, component_type)
            continue
        ptype: str = pinfo.get("type", "input")
        ntype: int = 0 if ptype == "input" else 1
        bw: int = _resolve_bw(pinfo.get("bitWidth", 1), params)
        nid: int = na.alloc(px, py, ntype, bw)
        pin_nodes[pname] = nid
        nodes_dict[pname] = nid

    # Build constructor params from reference
    ctor_params: list[Any] = [direction]
    for cp in comp_ref.get("constructor_params", []):
        cpname: str = cp["name"]
        if cpname == "direction":
            continue
        if cpname in params:
            ctor_params.append(params[cpname])
        elif "default" in cp and cp["default"] is not None:
            ctor_params.append(cp["default"])

    comp: CompDict = CompDict.create(component_type, x, y, ctor_params, nodes_dict,
        propagation_delay=propagation_delay, direction=direction, label=label)
    return comp, pin_nodes
