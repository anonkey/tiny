"""Waveform rendering: 1-bit, multi-bit, and time axis."""

from formatting import parse_value, format_time


def build_slot_map(all_signals_tv, t_start, t_end, cols, fmt="hex"):
    """Build a non-linear time->column mapping sized to fit value labels.

    Collects all transitions from all signals. Each slot is sized to fit
    its widest value label. If too many transitions to fit, shows the first N.

    Returns: sorted list of times, and a function time->col.
    """
    # Collect all transition times where value actually changed
    times_set = set()
    sig_vals = []  # per-signal: list of (time, formatted_value)
    for tv in all_signals_tv:
        vals = []
        prev_val = None
        for t, v in tv:
            if t < t_start:
                prev_val = v
                continue
            if t > t_end:
                break
            if v != prev_val:
                times_set.add(t)
                vals.append((t, parse_value(v, fmt)))
                prev_val = v
        sig_vals.append(vals)
    times_set.add(t_start)
    times = sorted(times_set)

    if len(times) <= 1:
        return times, lambda t: 0

    # For each slot, find the max label width across all signals
    slot_widths = []
    for idx in range(len(times)):
        max_label = 0
        for sv in sig_vals:
            label = ""
            for t, lbl in sv:
                if t <= times[idx]:
                    label = lbl
                else:
                    break
            if len(label) > max_label:
                max_label = len(label)
        # Minimum: 2 cols (transition + 1 char); with label: marker + pad + label + pad
        width = max(2, max_label + 3) if max_label > 0 else 2
        slot_widths.append(width)

    # Trim slots that don't fit
    total = 0
    n_fit = 0
    for w in slot_widths:
        if total + w > cols:
            break
        total += w
        n_fit += 1
    if n_fit < 1:
        n_fit = 1
    times = times[:n_fit]
    slot_widths = slot_widths[:n_fit]

    # Distribute remaining columns evenly
    total_min = sum(slot_widths)
    extra = cols - total_min
    if extra > 0:
        per_slot = extra // len(slot_widths)
        remainder = extra % len(slot_widths)
        for i in range(len(slot_widths)):
            slot_widths[i] += per_slot + (1 if i < remainder else 0)

    # Build mapping: cumulative column positions
    time_to_col = {}
    col = 0
    for i, tm in enumerate(times):
        time_to_col[tm] = col
        col += slot_widths[i]

    def map_time(t):
        if t <= times[0]:
            return 0
        if t >= times[-1]:
            return time_to_col[times[-1]]
        lo, hi = 0, len(times) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if times[mid] <= t:
                lo = mid
            else:
                hi = mid - 1
        return time_to_col[times[lo]]

    return times, map_time


def render_1bit(tv, t_start, t_end, cols, map_time=None):
    """Render a 1-bit signal as Unicode waveform characters."""
    if not tv:
        return "_" * cols

    # Build sorted transitions within range
    vals = []  # (col_index, value) for each transition
    prev_val = "0"
    for t, v in tv:
        if t < t_start:
            prev_val = v
            continue
        if t > t_end:
            break
        if map_time:
            col = map_time(t)
        else:
            ps_per_col = (t_end - t_start) / cols if cols > 0 else 1
            col = int((t - t_start) / ps_per_col)
        col = min(col, cols - 1)
        vals.append((col, v))
    start_val = prev_val

    # Fill columns
    cur_val = start_val
    transition_at = {}  # col -> new_value
    for col, v in vals:
        transition_at[col] = v

    row = []
    for c in range(cols):
        if c in transition_at:
            new_val = transition_at[c]
            if cur_val in ("0", "x", "X", "z", "Z") and new_val == "1":
                row.append("\u2571")  # rising
            elif cur_val == "1" and new_val in ("0", "x", "X", "z", "Z"):
                row.append("\u2572")  # falling
            else:
                row.append("\u2594" if new_val == "1" else "_")
            cur_val = new_val
        else:
            row.append("\u2594" if cur_val == "1" else "_")

    return "".join(row)


def render_multibit(tv, t_start, t_end, cols, fmt, map_time=None):
    """Render a multi-bit signal as 3 lines: top rail, value, bottom rail.

    Returns a tuple of 3 strings (top, mid, bot), each `cols` characters wide.
    """
    if not tv:
        top = "\u2500" * cols
        mid = " " * cols
        bot = "\u2500" * cols
        return (top, mid, bot)

    # Build segments: (start_col, end_col, formatted_label)
    segments = []
    prev_val = "0"
    prev_col = 0

    for t, v in tv:
        if t < t_start:
            prev_val = v
            continue
        if t > t_end:
            break
        if v == prev_val and segments:
            continue
        if map_time:
            col = map_time(t)
        else:
            ps_per_col = (t_end - t_start) / cols if cols > 0 else 1
            col = int((t - t_start) / ps_per_col)
        col = min(col, cols - 1)
        if col > prev_col or not segments:
            segments.append((prev_col, col, parse_value(prev_val, fmt)))
            prev_col = col
        prev_val = v

    # Last segment to end
    if prev_col < cols:
        segments.append((prev_col, cols, parse_value(prev_val, fmt)))

    # Merge consecutive segments with the same label
    merged = []
    for start, end, label in segments:
        if merged and merged[-1][2] == label:
            merged[-1] = (merged[-1][0], end, label)
        else:
            merged.append((start, end, label))
    segments = merged

    # Render 3 rows
    top = [" "] * cols
    mid = [" "] * cols
    bot = [" "] * cols

    for start, end, label in segments:
        width = end - start
        if width <= 0:
            continue

        off = 0
        if start > 0:
            top[start] = "\u2565"
            mid[start] = "\u2551"
            bot[start] = "\u2568"
            off = 1

        inner = width - off
        for i in range(off, width):
            if start + i < cols:
                top[start + i] = "\u2500"
                bot[start + i] = "\u2500"

        shown = label
        if len(shown) > inner:
            shown = label[:max(1, inner)]
        if inner >= 1:
            pad_total = inner - len(shown)
            pad_l = pad_total // 2
            for j, ch in enumerate(shown):
                pos = start + off + pad_l + j
                if pos < cols:
                    mid[pos] = ch

    return ("".join(top), "".join(mid), "".join(bot))


def render_time_axis(t_start, t_end, cols, time_unit="ns", slot_times=None, map_time=None):
    """Render a time axis with tick marks, preventing label overlap."""
    axis = [" "] * cols

    ticks = []
    if slot_times and map_time and len(slot_times) > 1:
        num_ticks = min(10, cols // 12)
        if num_ticks < 2:
            num_ticks = 2
        n = len(slot_times)
        step = max(1, n // num_ticks)
        tick_indices = list(range(0, n, step))
        if tick_indices[-1] != n - 1:
            tick_indices.append(n - 1)
        for idx in tick_indices:
            t = slot_times[idx]
            col = map_time(t)
            ticks.append((col, format_time(t, time_unit)))
    else:
        num_ticks = min(10, cols // 12)
        if num_ticks < 2:
            num_ticks = 2
        for i in range(num_ticks + 1):
            col = int(i * (cols - 1) / num_ticks)
            t = t_start + i * (t_end - t_start) / num_ticks
            ticks.append((col, format_time(t, time_unit)))

    next_free = 0
    for col, label in ticks:
        if col < next_free:
            continue
        if col < cols:
            axis[col] = "|"
        start = col + 1
        for j, ch in enumerate(label):
            pos = start + j
            if pos < cols:
                axis[pos] = ch
        next_free = col + 1 + len(label) + 1

    return "".join(axis)
