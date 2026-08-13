from __future__ import annotations

import sys
from pathlib import Path

APP_VALUE_NAME = "Crosshair Tempo"
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def startup_command() -> str:
    """Return a command that works for both a packaged app and source runs."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    project_root = Path(__file__).resolve().parent.parent
    return f'cmd.exe /d /c "cd /d ""{project_root}"" && ""{sys.executable}"" -m crosshair_tempo"'


def set_start_with_windows(enabled: bool) -> bool:
    """Add or remove the per-user startup entry without requiring elevation."""
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, APP_VALUE_NAME, 0, winreg.REG_SZ, startup_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_VALUE_NAME)
                except FileNotFoundError:
                    pass
    except OSError:
        return False
    return True
