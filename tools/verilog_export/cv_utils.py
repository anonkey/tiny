"""Shared utilities for CircuitVerse export modules."""


def _extract_comp_params(comp_type, comp):
    """Extract dimension-relevant params from a component's constructorParamaters."""
    ctor = comp.get("customData", {}).get("constructorParamaters", [])
    params = {}
    if comp_type in ("Input", "Output", "ConstantVal"):
        if len(ctor) >= 2:
            bw = ctor[1]
            params["bitWidth"] = int(bw) if isinstance(bw, (int, str)) and str(bw).isdigit() else 1
    elif comp_type in ("Multiplexer", "Demultiplexer"):
        if len(ctor) >= 3 and not isinstance(ctor[2], list):
            params["controlSignalSize"] = int(ctor[2])
    elif comp_type == "Decoder":
        if len(ctor) >= 2:
            params["bitWidth"] = int(ctor[1]) if not isinstance(ctor[1], list) else 1
    elif comp_type == "Splitter":
        if len(ctor) >= 3 and isinstance(ctor[2], list):
            params["bitWidthSplit"] = ctor[2]
    elif comp_type in ("AndGate", "OrGate", "NandGate", "NorGate",
                        "XorGate", "XnorGate"):
        if len(ctor) >= 2:
            params["inputLength"] = int(ctor[1])
    return params
