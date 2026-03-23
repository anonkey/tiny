"""UUID helper for KiCad schematic generation."""

_uuid_counter = 0


def _uuid():
    global _uuid_counter
    _uuid_counter += 1
    return f"{_uuid_counter:08x}-0000-0000-0000-{_uuid_counter:012x}"
