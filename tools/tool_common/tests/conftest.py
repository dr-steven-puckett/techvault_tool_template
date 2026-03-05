"""pytest configuration for tool_common tests.

Adds tools/ to sys.path so ``from tool_common.stamp import ...`` works when
running pytest from any working directory.
"""
import sys
from pathlib import Path

# tools/tool_common/tests/ -> tools/tool_common/ -> tools/
_TOOLS_DIR = Path(__file__).resolve().parent.parent.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))
