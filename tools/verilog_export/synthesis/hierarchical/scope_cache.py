"""Content-addressed cache for routed CircuitVerse scopes.

Keyed by an MD5 of the Verilog source files.  Within a source-hash
directory, each Yosys module is stored under its module name so that
unchanged designs skip placement + A* routing entirely.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from typing import Any

from common.types import ScopeDict

_log: logging.Logger = logging.getLogger(__name__)


def _sources_md5(verilog_paths: list[str]) -> str:
    """MD5 over the concatenated contents of all source files."""
    h: hashlib._Hash = hashlib.md5()
    for p in sorted(verilog_paths):
        with open(p, "rb") as f:
            h.update(f.read())
    return h.hexdigest()


class ScopeCache:
    """Disk-backed scope cache keyed by source MD5.

    Cache layout::

        <cache_root>/
          <sources_md5>/
            <module_name_hash>.json   # one per Yosys module
    """

    def __init__(self, cache_root: str, verilog_paths: list[str]) -> None:
        self._root: str = cache_root
        self._md5: str = _sources_md5(verilog_paths)
        self._dir: str = os.path.join(cache_root, self._md5)
        os.makedirs(self._dir, exist_ok=True)
        # Prune stale cache dirs (different source hash)
        self._prune_stale()

    # -- public API ----------------------------------------------------------

    @staticmethod
    def _mod_key(mod_name: str) -> str:
        """Stable filename for a Yosys module name (may contain $ \\ etc.)."""
        return hashlib.md5(mod_name.encode()).hexdigest()

    def get(self, mod_name: str) -> dict[str, Any] | None:
        """Load a cached scope for *mod_name*, or return *None*.

        Returns {"scope": ScopeDict, "port_info": ..., "subcircuit_types": ...}
        or None on miss.
        """
        path: str = os.path.join(self._dir, f"{self._mod_key(mod_name)}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                data: dict[str, Any] = json.load(f)
            data["scope"] = ScopeDict.from_dict(data["scope"])
            _log.info("cache HIT  %s", mod_name)
            return data
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning("cache CORRUPT %s: %s — treating as miss", mod_name, exc)
            return None

    def put(self, mod_name: str, scope: ScopeDict,
            port_info: dict[str, Any],
            subcircuit_types: list[str]) -> None:
        """Persist a routed scope to disk."""
        path: str = os.path.join(self._dir, f"{self._mod_key(mod_name)}.json")
        data: dict[str, Any] = {
            "scope": scope.to_dict(),
            "port_info": port_info,
            "subcircuit_types": subcircuit_types,
        }
        with open(path, "w") as f:
            json.dump(data, f, separators=(",", ":"))
        _log.info("cache STORE %s", mod_name)

    # -- housekeeping --------------------------------------------------------

    def _prune_stale(self) -> None:
        """Remove cache dirs whose source hash differs from the current one."""
        if not os.path.isdir(self._root):
            return
        for name in os.listdir(self._root):
            p: str = os.path.join(self._root, name)
            if os.path.isdir(p) and name != self._md5:
                shutil.rmtree(p)
                _log.info("cache PRUNED stale %s", name)

    def clear(self) -> None:
        """Remove the current cache dir."""
        if os.path.isdir(self._dir):
            shutil.rmtree(self._dir)
            _log.info("cache CLEARED %s", self._md5[:12])
