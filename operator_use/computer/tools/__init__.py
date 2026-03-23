"""Computer-use tools for Windows/macOS GUI automation."""

import sys
from operator_use.tools import Tool

COMPUTER_TOOL: Tool | None = None

try:
    match sys.platform:
        case "win32":
            from operator_use.computer.tools.windows import computer as COMPUTER_TOOL
        case "darwin":
            from operator_use.computer.tools.macos import computer as COMPUTER_TOOL
except (ImportError, OSError):
    pass

__all__ = ["COMPUTER_TOOL"]
