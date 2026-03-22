"""Value parsing and time formatting utilities."""


def parse_value(raw, fmt):
    """Convert a raw binary string value to the requested format."""
    if raw in ("x", "X", "z", "Z"):
        return raw
    try:
        n = int(raw, 2) if all(c in "01" for c in raw) else int(raw)
    except ValueError:
        return raw
    if fmt == "bin":
        return f"0b{n:b}"
    elif fmt == "dec":
        return str(n)
    else:
        return f"0x{n:X}"


def format_time(t, base_unit):
    """Format a time value with auto-scaling (ps -> ns -> us -> ms)."""
    scales = [("ps", 1), ("ns", 1e3), ("us", 1e6), ("ms", 1e9)]
    if base_unit == "ns":
        scales = [("ns", 1), ("us", 1e3), ("ms", 1e6)]
    elif base_unit == "us":
        scales = [("us", 1), ("ms", 1e3)]

    # Pick the largest unit where the value is >= 1
    unit, factor = scales[0]
    for u, f in scales:
        if abs(t) >= f or f == 1:
            unit, factor = u, f
    val = t / factor
    if val == int(val):
        return f"{int(val)}{unit}"
    return f"{val:.1f}{unit}"
