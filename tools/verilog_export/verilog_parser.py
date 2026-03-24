"""Verilog parser: extract modules, ports, parameters and instances."""

import logging
import re

_log = logging.getLogger(__name__)


class Port:
    __slots__ = ("name", "direction", "width", "msb", "lsb", "raw_range")

    def __init__(self, name, direction, width=1, msb=0, lsb=0, raw_range=""):
        self.name = name
        self.direction = direction  # "input" | "output"
        self.width = width
        self.msb = msb
        self.lsb = lsb
        self.raw_range = raw_range  # e.g. "[7:0]" or "[N-1:0]"

    def label(self):
        if self.width > 1 or self.raw_range:
            rng = self.raw_range or f"[{self.msb}:{self.lsb}]"
            return f"{self.name}{rng}"
        return self.name


class Param:
    __slots__ = ("name", "default")

    def __init__(self, name, default=""):
        self.name = name
        self.default = default


class Instance:
    __slots__ = ("module_name", "inst_name", "params", "connections")

    def __init__(self, module_name, inst_name, params=None, connections=None):
        self.module_name = module_name
        self.inst_name = inst_name
        self.params = params or {}      # {param_name: value_str}
        self.connections = connections or {}  # {port_name: net_expr}


class Module:
    __slots__ = ("name", "params", "ports", "instances", "path")

    def __init__(self, name, params=None, ports=None, instances=None, path=""):
        self.name = name
        self.params = params or []
        self.ports = ports or []
        self.instances = instances or []
        self.path = path

    @property
    def inputs(self):
        return [p for p in self.ports if p.direction == "input"]

    @property
    def outputs(self):
        return [p for p in self.ports if p.direction == "output"]


def _strip_comments(text):
    """Remove // and /* */ comments."""
    text = re.sub(r'//.*', '', text)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    return text


def _match_balanced_parens(text, start):
    """From position of '(' at `start`, return the index after matching ')'."""
    depth = 0
    i = start
    while i < len(text):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


def _parse_dot_connections(text):
    """Parse '.name(expr)' pairs from a string, handling nested parens."""
    result = {}
    for m in re.finditer(r'\.(\w+)\s*\(', text):
        name = m.group(1)
        paren_start = m.end() - 1
        paren_end = _match_balanced_parens(text, paren_start)
        value = text[paren_start + 1:paren_end - 1].strip()
        result[name] = value
    return result


_INST_SKIP_KW = {
    'module', 'input', 'output', 'wire', 'reg', 'assign',
    'always', 'initial', 'function', 'endfunction', 'generate',
    'endgenerate', 'for', 'if', 'else', 'begin', 'end',
    'localparam', 'parameter', 'genvar', 'integer',
}


def _parse_instances(body):
    """Parse submodule instantiations from a module body, handling nested parens."""
    instances = []
    # Pattern: module_name [#(...)] inst_name (
    # We find candidates by looking for: word [#(...)] word (
    pat = re.compile(r'(\w+)\s*(#\s*\()?')
    pos = 0
    while pos < len(body):
        m = pat.match(body, pos)
        if not m:
            pos += 1
            continue

        mtype = m.group(1)
        if mtype in _INST_SKIP_KW:
            pos = m.end()
            continue

        has_params = m.group(2) is not None

        if has_params:
            # Find matching ')' for the #( block
            param_paren_start = body.index('(', m.start(2))
            param_paren_end = _match_balanced_parens(body, param_paren_start)
            param_str = body[param_paren_start + 1:param_paren_end - 1]
            rest_start = param_paren_end
        else:
            param_str = ""
            rest_start = m.end()

        # After params: expect inst_name then '('
        rest = body[rest_start:].lstrip()
        inst_m = re.match(r'(\w+)\s*\(', rest)
        if not inst_m:
            pos = rest_start + 1
            continue

        iname = inst_m.group(1)
        if iname in _INST_SKIP_KW:
            pos = rest_start + 1
            continue

        conn_paren_start = rest_start + rest.index('(', inst_m.start())
        conn_paren_end = _match_balanced_parens(body, conn_paren_start)
        conn_str = body[conn_paren_start + 1:conn_paren_end - 1]

        # Check for semicolon after
        after = body[conn_paren_end:conn_paren_end + 10].lstrip()
        if not after.startswith(';'):
            pos = conn_paren_end
            continue

        inst_params = _parse_dot_connections(param_str)
        connections = _parse_dot_connections(conn_str)
        instances.append(Instance(mtype, iname, inst_params, connections))

        pos = conn_paren_end + 1

    return instances


def _eval_width(expr, params):
    """Try to evaluate a width expression given parameter defaults."""
    expr = expr.strip()
    if not expr:
        return 1, expr
    # Replace parameter names with defaults
    env = {}
    for p in params:
        try:
            env[p.name] = int(p.default)
        except (ValueError, TypeError):
            _log.debug("_eval_width: cannot convert param '%s' default '%s' to int",
                       p.name, p.default)
    # Handle $clog2
    def clog2_sub(m):
        inner = m.group(1)
        try:
            val = eval(inner, {"__builtins__": {}}, env)
            return str(max(1, (val - 1).bit_length()))
        except Exception:
            _log.debug("_eval_width: $clog2 evaluation failed for '%s'", inner)
            return m.group(0)
    expr_eval = re.sub(r'\$clog2\(([^)]+)\)', clog2_sub, expr)
    try:
        val = eval(expr_eval, {"__builtins__": {}}, env)
        return int(val), f"[{expr}]"
    except Exception:
        _log.debug("_eval_width: expression evaluation failed for '%s'", expr_eval)
        return 1, f"[{expr}]"


def parse_verilog(filepath):
    """Parse a Verilog file and return a list of Module objects."""
    with open(filepath) as f:
        text = f.read()
    text = _strip_comments(text)
    modules = []

    # Split by module...endmodule
    mod_blocks = re.finditer(
        r'module\s+(\w+)\s*(#\s*\(.*?\))?\s*\((.*?)\)\s*;(.*?)endmodule',
        text, re.DOTALL
    )

    for mb in mod_blocks:
        mod_name = mb.group(1)
        param_block = mb.group(2) or ""
        port_block = mb.group(3) or ""
        body = mb.group(4) or ""

        # --- Parameters ---
        params = []
        # From #(...) header
        for pm in re.finditer(r'parameter\s+(\w+)\s*=\s*([^,\)]+)', param_block):
            params.append(Param(pm.group(1), pm.group(2).strip()))
        # From body (old-style)
        for pm in re.finditer(r'^\s*parameter\s+(\w+)\s*=\s*([^;]+);', body, re.MULTILINE):
            if not any(p.name == pm.group(1) for p in params):
                params.append(Param(pm.group(1), pm.group(2).strip()))

        # --- Ports ---
        ports = []

        # Modern style: direction [range] name in port block
        # Also handle: output wire, output reg, input wire
        modern = re.findall(
            r'(input|output)\s+(?:wire|reg)?\s*(\[[^\]]*\])?\s*(\w+)',
            port_block
        )
        if modern:
            for direction, rng, name in modern:
                if rng:
                    inner = rng.strip("[]")
                    parts = inner.split(":")
                    if len(parts) == 2:
                        width, raw = _eval_width(f"{parts[0]} - {parts[1]} + 1", params)
                        # Try numeric msb:lsb
                        try:
                            msb = int(eval(parts[0].strip(), {"__builtins__": {}},
                                          {p.name: int(p.default) for p in params if p.default.strip().isdigit()}))
                            lsb = int(eval(parts[1].strip(), {"__builtins__": {}},
                                          {p.name: int(p.default) for p in params if p.default.strip().isdigit()}))
                            width = msb - lsb + 1
                        except Exception:
                            _log.debug("parse_verilog: width eval failed for port '%s' range '%s'",
                                       name, rng)
                        ports.append(Port(name, direction, width, msb=0, lsb=0, raw_range=rng))
                    else:
                        ports.append(Port(name, direction, 1, raw_range=rng))
                else:
                    ports.append(Port(name, direction, 1))
        else:
            # Old-style: port names in module(...), declarations in body
            port_names = [n.strip() for n in port_block.split(",") if n.strip()]
            # Find declarations in body
            for decl in re.finditer(
                r'(input|output)\s+(?:wire|reg)?\s*(\[[^\]]*\])?\s*([^;]+);',
                body
            ):
                direction = decl.group(1)
                rng = decl.group(2) or ""
                names_str = decl.group(3)
                for name in names_str.split(","):
                    name = name.strip()
                    if not name or name not in port_names:
                        continue
                    if rng:
                        inner = rng.strip("[]")
                        parts = inner.split(":")
                        width = 1
                        if len(parts) == 2:
                            try:
                                env = {p.name: int(p.default) for p in params
                                       if p.default.strip().isdigit()}
                                msb = int(eval(parts[0].strip(), {"__builtins__": {}}, env))
                                lsb = int(eval(parts[1].strip(), {"__builtins__": {}}, env))
                                width = msb - lsb + 1
                            except Exception:
                                _log.debug("parse_verilog: width eval failed for old-style port '%s' range '%s'",
                                           name, rng)
                        ports.append(Port(name, direction, width, raw_range=rng))
                    else:
                        ports.append(Port(name, direction, 1))

        # --- Submodule instances ---
        instances = []
        instances = _parse_instances(body)

        modules.append(Module(mod_name, params, ports, instances, filepath))

    return modules
