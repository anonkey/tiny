"""Signal matching with interactive selection."""

import fnmatch
import sys

from resolution import interactive_select


def match_signals(all_signals, patterns, interactive=True):
    """Match signal names against patterns. Prompts interactively if too many matches."""
    matched = []
    for pat in patterns:
        # Exact full-path match
        if pat in all_signals:
            matched.append(pat)
            continue

        # Exact leaf-name match (e.g. "clk" matches "tb.dut.clk" but not "tb.dut.sclk")
        leaf_exact = sorted(
            s for s in all_signals if s.rsplit(".", 1)[-1] == pat
        )
        if leaf_exact:
            # Prefer the shallowest (top-level) match
            leaf_exact.sort(key=lambda s: (s.count("."), s))
            if len(leaf_exact) == 1 or not interactive:
                matched.extend(leaf_exact[:1] if interactive else leaf_exact)
                continue
            # Multiple exact leaf matches — pick shallowest automatically
            matched.append(leaf_exact[0])
            continue

        # Glob match
        found = sorted(s for s in all_signals if fnmatch.fnmatch(s, pat))
        if found:
            matched.extend(found)
            continue

        # Substring match on leaf name first, then full path
        leaf_sub = sorted(
            s for s in all_signals if pat in s.rsplit(".", 1)[-1]
        )
        found = leaf_sub if leaf_sub else sorted(s for s in all_signals if pat in s)
        if not found:
            print(f"warning: no signal matching '{pat}'", file=sys.stderr)
            continue

        # If many matches and interactive, let user select
        if interactive and len(found) > 10:
            found.sort(key=lambda s: (s.count("."), s))
            top = found[:20]
            print(f"'{pat}' matches {len(found)} signals. Showing top {len(top)}:", file=sys.stderr)
            selected = interactive_select("Select signal:", top)
            matched.append(selected)
        else:
            matched.extend(found)

    # Deduplicate preserving order
    seen = set()
    result = []
    for s in matched:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result
