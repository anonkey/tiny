"""CircuitVerse component handlers for Yosys cell types."""

from synthesis.gates.logic import place_logic
from synthesis.gates.mux import place_mux
from synthesis.gates.arithmetic import place_add, place_sub, place_mul, place_divmod, place_neg
from synthesis.gates.shift import place_shift
from synthesis.gates.compare import place_eq_ne, place_lt_gt_le_ge
from synthesis.gates.reduce import place_reduce, place_logic_not, place_logic_and_or
from synthesis.gates.dff import place_dff
from synthesis.gates.bus import place_slice, place_concat, place_cv_splitter
from synthesis.gates.mem import place_mem_v2
from synthesis.gates.gate_primitives import place_gate_logic, place_gate_mux, place_gate_dff

from common.constants import (
  _new_pin, _new_bus_pin, _param_int, _param_bits,
  _YOSYS_DFF_PREFIX,
)
