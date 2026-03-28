"""CircuitVerse scope ID allocator, layout, and scope builder."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import verilog_parser

from common.node_alloc import _CVNodeAlloc
from common.emit import CTOR_PARAMS_KEY
from common.types import CompDict, CVCustomData, ScopeDict, VerilogMetadata, LayoutDict, PinPos


class _CVScopeCounter:
    """Sequential scope-ID allocator for CircuitVerse."""

    _SCOPE_ID_BASE = 10_000_000_000  # high base avoids collisions with CV internals

    _counter: int

    def __init__(self) -> None:
        self._counter = -1

    def __call__(self) -> str:
        self._counter += 1
        return str(self._SCOPE_ID_BASE + self._counter)

    def reset(self) -> None:
        self._counter = -1

_cv_scope_id: _CVScopeCounter = _CVScopeCounter()


def _cv_layout(n_inputs: int, n_outputs: int) -> LayoutDict:
    """Compute subcircuit layout block size."""
    n_max = max(n_inputs, n_outputs, 1)
    return {
        "width": 100,
        "height": 20 * n_max + 40,
        "title_x": 50,
        "title_y": 13,
        "titleEnabled": True,
    }


def _build_cv_scope(
    mod: verilog_parser.Module, na: _CVNodeAlloc
) -> tuple[ScopeDict, str, dict[str, PinPos]]:
    """Build a CircuitVerse scope dict for a Module (subcircuit definition).

    Returns (scope_dict, scope_id, pin_positions).
    pin_positions maps port_name -> {"x": ..., "y": ...} for SubCircuit node
    placement in the parent.
    """
    scope_id = _cv_scope_id()
    sna = _CVNodeAlloc()
    layout = _cv_layout(len(mod.inputs), len(mod.outputs))
    layout_w = layout["width"]

    inputs: list[CompDict] = []
    outputs: list[CompDict] = []
    pin_positions: dict[str, PinPos] = {}  # port_name -> {x, y} on the SubCircuit box

    pin_y: int = 40
    for p in mod.inputs:
        out_node = sna.alloc(10, 0, 1, p.width)
        bw = str(p.width) if p.width > 1 else 1
        pin_positions[p.name] = {"x": 0, "y": pin_y}
        inputs.append(CompDict(
            x=-20, y=pin_y - 20,
            objectType="Input", label=p.name,
            direction="RIGHT", labelDirection="LEFT",
            propagationDelay=0,
            customData=CVCustomData(
                constructorParamaters=[
                    "RIGHT", bw,
                    {"x": 0, "y": pin_y, "id": f"sc_{mod.name}_{p.name}"},
                ],
                nodes={"output1": out_node},
                values={"state": 0},
            ),
        ))
        pin_y += 20

    pin_y = 40
    for p in mod.outputs:
        inp_node = sna.alloc(-10, 0, 0, p.width)
        bw = str(p.width) if p.width > 1 else 1
        pin_positions[p.name] = {"x": layout_w, "y": pin_y}
        outputs.append(CompDict(
            x=layout_w + 20, y=pin_y - 20,
            objectType="Output", label=p.name,
            direction="LEFT", labelDirection="RIGHT",
            propagationDelay=0,
            customData=CVCustomData(
                constructorParamaters=[
                    "LEFT", bw,
                    {"x": layout_w, "y": pin_y, "id": f"sc_{mod.name}_{p.name}"},
                ],
                nodes={"inp1": inp_node},
            ),
        ))
        pin_y += 20

    scope: ScopeDict = ScopeDict(
        layout=layout,
        verilogMetadata=VerilogMetadata(),
        allNodes=sna.nodes,
        id=int(scope_id),
        name=mod.name,
        nodes=sorted(
            i for i, n in enumerate(sna.nodes)
            if n.type == 2 and n.connections
        ),
        components={
            "Input": list(inputs),
            "Output": list(outputs),
        },
    )
    return scope, scope_id, pin_positions
