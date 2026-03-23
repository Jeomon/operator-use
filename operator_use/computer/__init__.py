"""Computer-use Desktop and Tree services for Windows/macOS."""

import sys

Desktop = None
WatchDog = None

try:
    match sys.platform:
        case "win32":
            from operator_use.computer.windows.desktop.service import Desktop
            from operator_use.computer.windows.watchdog.service import WatchDog
        case "darwin":
            from operator_use.computer.macos.desktop.service import Desktop
            from operator_use.computer.macos.watchdog.service import WatchDog
        case "linux":
            from operator_use.computer.linux.desktop.service import Desktop
        case _:
            pass
except (ImportError, OSError):
    pass

__all__ = ["Desktop", "WatchDog"]
