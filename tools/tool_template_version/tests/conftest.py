"""pytest configuration for tool_template_version tests.

Adds tools/ and tools/tool_template_version/ to sys.path so that
``import versioner`` and ``from tool_common.stamp import ...`` both work
when running pytest from any working directory.
"""
import sys
from pathlib import Path

_TOOL_DIR = Path(__file__).resolve().parent.parent   # tools/tool_template_version/
_TOOLS_DIR = _TOOL_DIR.parent                         # tools/

for _p in (str(_TOOLS_DIR), str(_TOOL_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
