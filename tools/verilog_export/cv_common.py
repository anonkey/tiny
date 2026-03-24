"""Re-export facade for backward compatibility.

The actual implementations now live in:
  cv_node_alloc  — _CVNodeAlloc
  cv_scope       — _CVScopeCounter, _cv_scope_id, _cv_layout, _build_cv_scope
  cv_emit        — emit_constant, emit_not_gate, emit_zero_extend,
                   register_bits, unique_pos, emit_splitter,
                   emit_split_reduce, emit_component
"""

from cv_node_alloc import _CVNodeAlloc
from cv_scope import _CVScopeCounter, _cv_scope_id, _cv_layout, _build_cv_scope
from cv_emit import (
    emit_constant, emit_not_gate, emit_zero_extend,
    register_bits, unique_pos, emit_splitter, emit_split_reduce,
    emit_component,
)
