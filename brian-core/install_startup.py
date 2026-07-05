"""
Brian AI Assistant — Windows Startup Installer
Registers Brian to auto-start with Windows via the registry.
Run this once: python install_startup.py
"""

import sys
import os
import winreg
import subprocess
from pathlib import Path

BRIAN_CORE_DIR = Path(__file__).parent.resolve()
BAT_PATH       = BRIAN_CORE_DIR / "start_brian.bat"
REG_KEY        = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_VALUE      = "BrianAI"


def create_bat():
    """Create the start_brian.bat launcher."""
    python_exe = sys.executable
    main_py    = BRIAN_CORE_DIR / "main.py"

    bat_content = f"""@echo off
title BRIAN AI Assistant
cd /d "{BRIAN_CORE_DIR}"
"{python_exe}" "{main_py}"
"""
    with open(BAT_PATH, "w") as f:
        f.write(bat_content)
    print(f"[OK] Launcher created: {BAT_PATH}")


def register_startup():
    """Add Brian to Windows startup registry."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REG_KEY,
            0,
            winreg.KEY_SET_VALUE
        )
        # Prefer venv pythonw.exe to ensure packages are loaded on startup
        venv_pythonw = BRIAN_CORE_DIR / "venv" / "Scripts" / "pythonw.exe"
        if venv_pythonw.exists():
            pythonw = venv_pythonw
        else:
            pythonw = Path(sys.executable).parent / "pythonw.exe"
            if not pythonw.exists():
                pythonw = sys.executable

        main_py = BRIAN_CORE_DIR / "main.py"
        cmd     = f'"{pythonw}" "{main_py}"'

        winreg.SetValueEx(key, REG_VALUE, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        print(f"[OK] Registered in Windows startup: {cmd}")
    except Exception as e:
        print(f"[ERROR] Could not register startup: {e}")
        print("   Try running as Administrator.")


def unregister_startup():
    """Remove Brian from Windows startup."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REG_KEY,
            0,
            winreg.KEY_SET_VALUE
        )
        try:
            winreg.DeleteValue(key, REG_VALUE)
            print("[OK] Removed BRIAN from Windows startup.")
        except FileNotFoundError:
            print("[INFO] BRIAN was not in startup registry.")
        winreg.CloseKey(key)
    except Exception as e:
        print(f"[ERROR] Error: {e}")


if __name__ == "__main__":
    if "--uninstall" in sys.argv:
        unregister_startup()
    else:
        create_bat()
        register_startup()
        print("\n[OK] BRIAN will now start automatically with Windows!")
        print("   To remove: python install_startup.py --uninstall")
