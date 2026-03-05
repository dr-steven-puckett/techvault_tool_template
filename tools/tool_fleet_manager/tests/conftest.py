"""pytest configuration for tool_fleet_manager tests.

Adds tools/ and tools/tool_fleet_manager/ to sys.path so that
``import fleet`` and ``from tool_common.report import ...`` both work
when running pytest from any working directory.
"""
import sys
from pathlib import Path

_TOOL_DIR = Path(__file__).resolve().parent.parent   # tools/tool_fleet_manager/
_TOOLS_DIR = _TOOL_DIR.parent                         # tools/

for _p in (str(_TOOLS_DIR), str(_TOOL_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
