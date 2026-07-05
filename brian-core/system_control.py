"""
Brian AI Assistant — System Control
Full Windows system control: open apps, folders, websites, type text,
control volume, take screenshots, run shell commands.
"""

import os
import subprocess
import webbrowser
import pyautogui
import psutil
import logging
import platform
import ctypes
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Common Windows app aliases → executable names
APP_ALIASES = {
    "notepad":        "notepad.exe",
    "calculator":     "calc.exe",
    "paint":          "mspaint.exe",
    "word":           "winword.exe",
    "excel":          "excel.exe",
    "powerpoint":     "powerpnt.exe",
    "outlook":        "outlook.exe",
    "teams":          "teams.exe",
    "discord":        "discord.exe",
    "spotify":        "spotify.exe",
    "chrome":         "chrome.exe",
    "firefox":        "firefox.exe",
    "edge":           "msedge.exe",
    "brave":          "brave.exe",
    "explorer":       "explorer.exe",
    "task manager":   "taskmgr.exe",
    "cmd":            "cmd.exe",
    "terminal":       "wt.exe",
    "powershell":     "powershell.exe",
    "vs code":        "vscode",
    "vscode":         "vscode",
    "visual studio code": "vscode",
    "visual studio":  "devenv.exe",
    "obs":            "obs64.exe",
    "vlc":            "vlc.exe",
    "zoom":           "zoom.exe",
    "settings":       "ms-settings:",
    "control panel":  "control.exe",
    "file manager":   "explorer.exe",
    "files":          "explorer.exe",
    # Brian Custom Subsystems
    "brian ide":      "http://localhost:9003",
    "brian editor":   "http://localhost:9003",
    "brian ide editor": "http://localhost:9003",
    "brian hud":      "http://localhost:9001",
    "brian panel":    "http://localhost:9001",
    "brian control panel": "http://localhost:9001",
}

# Common folder aliases
FOLDER_ALIASES = {
    "desktop":    Path.home() / "Desktop",
    "downloads":  Path.home() / "Downloads",
    "documents":  Path.home() / "Documents",
    "pictures":   Path.home() / "Pictures",
    "music":      Path.home() / "Music",
    "videos":     Path.home() / "Videos",
    "home":       Path.home(),
    "appdata":    Path(os.getenv("APPDATA", "")),
    "temp":       Path(os.getenv("TEMP", "")),
    "c drive":    Path("C:\\"),
    "c:":         Path("C:\\"),
}

# Web fallback URLs for common applications when not installed locally
WEB_FALLBACKS = {
    "spotify": "https://open.spotify.com",
    "discord": "https://discord.com/app",
    "youtube": "https://youtube.com",
    "netflix": "https://netflix.com",
    "whatsapp": "https://web.whatsapp.com",
    "telegram": "https://web.telegram.org",
}


def _resolve_app_path(exe_name: str) -> Optional[str]:
    """Helper to locate an executable path using Registry App Paths, common install directories, and Start Menu shortcuts."""
    import winreg
    import shutil

    # 1. Check if it's already in the system PATH
    found = shutil.which(exe_name)
    if found:
        return found

    # 2. Check Windows Registry App Paths (Official way Windows launches registered apps)
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        sub_key = f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{exe_name}"
        try:
            with winreg.OpenKey(root, sub_key) as key:
                val, _ = winreg.QueryValueEx(key, "")
                if val and os.path.exists(val):
                    return val
        except OSError:
            continue

    # 3. Check common folder fallbacks
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
    appdata = os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))

    paths_to_check = [
        # Chrome
        os.path.join(program_files, "Google\\Chrome\\Application", exe_name),
        os.path.join(program_files_x86, "Google\\Chrome\\Application", exe_name),
        # Edge
        os.path.join(program_files_x86, "Microsoft\\Edge\\Application", exe_name),
        os.path.join(program_files, "Microsoft\\Edge\\Application", exe_name),
        # Firefox
        os.path.join(program_files, "Mozilla Firefox", exe_name),
        os.path.join(program_files_x86, "Mozilla Firefox", exe_name),
        # VS Code
        os.path.join(local_appdata, "Programs\\Microsoft VS Code", "Code.exe"),
        os.path.join(program_files, "Microsoft VS Code", "Code.exe"),
        # Spotify Desktop Client
        os.path.join(appdata, "Spotify", "Spotify.exe"),
        os.path.join(local_appdata, "Spotify", "Spotify.exe"),
        os.path.join(local_appdata, "Microsoft\\WindowsApps", "Spotify.exe"),
    ]

    for p in paths_to_check:
        if os.path.exists(p) and p.lower().endswith(exe_name.lower()):
            return p

    # 4. Scan Start Menu for shortcuts (.lnk files)
    start_menu_paths = [
        os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), "Microsoft\\Windows\\Start Menu\\Programs"),
        os.path.join(appdata, "Microsoft\\Windows\\Start Menu\\Programs")
    ]
    app_base_name = exe_name.lower().replace(".exe", "")

    for start_menu in start_menu_paths:
        if os.path.exists(start_menu):
            for root_dir, _, files in os.walk(start_menu):
                for f in files:
                    if f.lower().endswith(".lnk") and app_base_name in f.lower():
                        shortcut_path = os.path.join(root_dir, f)
                        logger.info(f"Found Start Menu shortcut for {exe_name}: {shortcut_path}")
                        return shortcut_path

    return None


def open_application(app_name: str) -> dict:
    """Open a Windows application by name or alias, falling back to web player/app if not installed."""
    try:
        app_lower = app_name.lower().strip()
        exe = APP_ALIASES.get(app_lower, None)

        if not exe:
            # If no alias, treat app_name itself as the executable/alias
            exe = app_name if app_name.lower().endswith(".exe") else f"{app_name}.exe"

        if exe.startswith(("http://", "https://")):
            webbrowser.open(exe)
            return {"success": True, "action": f"Opened browser to {exe}"}

        # Resolve VS Code directly
        if app_lower in ("vscode", "vs code", "visual studio code") or exe.lower() in ("code.exe", "code"):
            exe = "Code.exe"

        # Resolve path robustly (including Start Menu shortcuts)
        resolved_path = _resolve_app_path(exe)
        
        if resolved_path:
            logger.info(f"Resolved app path: {resolved_path}")
            os.startfile(resolved_path)
            return {"success": True, "action": f"Opened {app_name} via {resolved_path}"}
        
        # If not found locally, check if we have a web fallback (e.g. Spotify -> Web Spotify)
        for key, url in WEB_FALLBACKS.items():
            if key in app_lower or key in exe.lower():
                logger.info(f"App {app_name} not installed locally. Redirecting to Web Fallback: {url}")
                webbrowser.open(url)
                return {"success": True, "action": f"Redirected {app_name} to web version: {url}"}

        # Last-resort: try running os.startfile directly (handles system URLs/custom protocols like spotify:)
        try:
            logger.info(f"Attempting direct startfile for {exe}")
            os.startfile(exe)
            return {"success": True, "action": f"Opened {app_name} via protocol/system link"}
        except Exception:
            # Last-resort fallback to cmd shell start
            logger.warning(f"Could not resolve or direct-open {exe}. Falling back to Shell Start.")
            subprocess.Popen(f'start "" "{exe}"', shell=True)
            return {"success": True, "action": f"Attempted shell start of {app_name}"}

    except Exception as e:
        logger.error(f"open_application error: {e}")
        return {"success": False, "error": str(e)}


def open_website(url: str) -> dict:
    """Open a website in the default browser."""
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        import webbrowser
        import subprocess
        # Try both webbrowser and Windows shell start to ensure execution in active session
        try:
            webbrowser.open(url)
        except Exception:
            pass
        subprocess.Popen(f'cmd.exe /c start {url}', shell=True)
        return {"success": True, "action": f"Opened {url}"}
    except Exception as e:
        logger.error(f"open_website error: {e}")
        return {"success": False, "error": str(e)}


def open_folder(folder_name: str) -> dict:
    """Open a folder in Windows Explorer."""
    try:
        folder_lower = folder_name.lower().strip()
        path = FOLDER_ALIASES.get(folder_lower, None)

        if path is None:
            # Try as a direct path
            path = Path(folder_name)

        if path.exists():
            subprocess.Popen(f'explorer "{path}"', shell=True)
            return {"success": True, "action": f"Opened folder: {path}"}
        else:
            return {"success": False, "error": f"Folder not found: {path}"}
    except Exception as e:
        logger.error(f"open_folder error: {e}")
        return {"success": False, "error": str(e)}


def type_text(text: str, interval: float = 0.03) -> dict:
    """Type text using pyautogui."""
    try:
        import time
        time.sleep(0.5)  # Small delay to let focus settle
        pyautogui.typewrite(text, interval=interval)
        return {"success": True, "action": f"Typed: {text}"}
    except Exception as e:
        logger.error(f"type_text error: {e}")
        return {"success": False, "error": str(e)}


def take_screenshot(save_path: Optional[str] = None) -> dict:
    """Take a screenshot and return the path."""
    try:
        screenshot = pyautogui.screenshot()
        if save_path is None:
            save_path = str(Path.home() / "Desktop" / "brian_screenshot.png")
        screenshot.save(save_path)
        return {"success": True, "path": save_path, "action": "Screenshot taken"}
    except Exception as e:
        logger.error(f"take_screenshot error: {e}")
        return {"success": False, "error": str(e)}


def run_shell_command(command: str, timeout: int = 30) -> dict:
    """Run a PowerShell or CMD command."""
    try:
        result = subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "success": True,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
            "action": f"Ran command: {command}"
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out"}
    except Exception as e:
        logger.error(f"run_shell_command error: {e}")
        return {"success": False, "error": str(e)}


def set_volume(level: int) -> dict:
    """Set system volume (0–100)."""
    try:
        level = max(0, min(100, level))
        # Use nircmd if available, fallback to PowerShell
        script = f"""
        $wshShell = New-Object -ComObject WScript.Shell
        $volume = {level}
        Add-Type -TypeDefinition @"
        using System.Runtime.InteropServices;
        [Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IAudioEndpointVolume {{ [PreserveSig] int NotImpl1(); [PreserveSig] int NotImpl2();
        [PreserveSig] int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext);
        [PreserveSig] int NotImpl3(); [PreserveSig] int GetMasterVolumeLevelScalar(out float pfLevel); }}
        [Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IMMDevice {{ [PreserveSig] int Activate(ref System.Guid id, int clsCtx, int activationParams, out IAudioEndpointVolume aev); }}
        [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IMMDeviceEnumerator {{ [PreserveSig] int NotImpl1();
        [PreserveSig] int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice endpoint); }}
        [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class MMDeviceEnumeratorComObject {{ }}
        public class Audio {{
            static IAudioEndpointVolume Vol() {{
                var enumerator = new MMDeviceEnumeratorComObject() as IMMDeviceEnumerator;
                IMMDevice dev = null; enumerator.GetDefaultAudioEndpoint(0, 1, out dev);
                IAudioEndpointVolume vol = null; var domainId = typeof(IAudioEndpointVolume).GUID;
                dev.Activate(ref domainId, 23, 0, out vol); return vol; }}
            public static void SetVolume(double level) {{ Vol().SetMasterVolumeLevelScalar((float)level, System.Guid.Empty); }}
        }}
"@
        [Audio]::SetVolume({level} / 100)
        """
        result = subprocess.run(
            ["powershell", "-Command", script],
            capture_output=True, text=True, timeout=10
        )
        return {"success": True, "action": f"Volume set to {level}%"}
    except Exception as e:
        logger.error(f"set_volume error: {e}")
        return {"success": False, "error": str(e)}


def get_running_processes() -> dict:
    """Get list of currently running processes."""
    try:
        procs = [p.name() for p in psutil.process_iter(['name']) if p.info['name']]
        unique = sorted(set(procs))
        return {"success": True, "processes": unique}
    except Exception as e:
        return {"success": False, "error": str(e)}


def close_application(app_name: str) -> dict:
    """Close a running application by process name."""
    try:
        closed = False
        for proc in psutil.process_iter(['name', 'pid']):
            if app_name.lower() in proc.info['name'].lower():
                proc.terminate()
                closed = True
        if closed:
            return {"success": True, "action": f"Closed {app_name}"}
        return {"success": False, "error": f"{app_name} not found in running processes"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def press_keys(keys: str) -> dict:
    """Press keyboard shortcuts (e.g., 'ctrl+c', 'alt+f4', 'win+d')."""
    try:
        key_list = [k.strip() for k in keys.lower().split("+")]
        pyautogui.hotkey(*key_list)
        return {"success": True, "action": f"Pressed {keys}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def lock_screen() -> dict:
    """Lock the Windows screen."""
    try:
        ctypes.windll.user32.LockWorkStation()
        return {"success": True, "action": "Screen locked"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def shutdown_pc(delay_seconds: int = 0) -> dict:
    """Shutdown the PC."""
    try:
        subprocess.run(f"shutdown /s /t {delay_seconds}", shell=True)
        return {"success": True, "action": f"Shutdown scheduled in {delay_seconds}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def restart_pc(delay_seconds: int = 0) -> dict:
    """Restart the PC."""
    try:
        subprocess.run(f"shutdown /r /t {delay_seconds}", shell=True)
        return {"success": True, "action": f"Restart scheduled in {delay_seconds}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def write_and_paste_text(text: str, destination: str = "cursor") -> dict:
    """Write text/code by copying to clipboard and pasting it at the cursor or inside Notepad."""
    try:
        import time
        import pyperclip
        import pyautogui

        # If notepad, open notepad first
        if destination.lower() == "notepad":
            logger.info("Opening Notepad for writing text...")
            open_application("notepad")
            time.sleep(1.0)  # Wait for notepad window to appear and capture focus

        # Save current clipboard content to restore it later
        old_clipboard = pyperclip.paste()

        # Copy the target text to clipboard
        pyperclip.copy(text)
        time.sleep(0.1)

        # Paste via keyboard shortcut
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.1)

        # Restore original clipboard
        if old_clipboard:
            pyperclip.copy(old_clipboard)

        return {"success": True, "action": f"Pasted text to {destination}"}
    except Exception as e:
        logger.error(f"write_and_paste_text error: {e}")
        return {"success": False, "error": str(e)}


def get_selected_or_page_text() -> dict:
    """Gets the active window title and any text selected or on the page using clipboard copy simulation."""
    try:
        import time
        import pyperclip
        import pyautogui
        import win32gui

        # 1. Get active window title
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)

        # Save current clipboard content to restore it later
        old_clipboard = pyperclip.paste()

        # Clear clipboard to detect if new copy succeeds
        pyperclip.copy("")
        time.sleep(0.1)

        # Try copying selected text first (Ctrl+C)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.2)
        copied_text = pyperclip.paste().strip()

        method = "selected_text"

        # If no selected text, try select all and copy (Ctrl+A, Ctrl+C)
        if not copied_text:
            logger.info("No selected text found. Attempting select-all and copy...")
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
            pyautogui.hotkey("ctrl", "c")
            time.sleep(0.2)
            copied_text = pyperclip.paste().strip()
            method = "page_text"

        # Restore original clipboard
        if old_clipboard:
            pyperclip.copy(old_clipboard)

        # Limit return length if extremely long to avoid LLM context bloating
        if len(copied_text) > 10000:
            copied_text = copied_text[:10000] + "\n...[TRUNCATED due to length]..."

        return {
            "success": True,
            "active_window_title": title,
            "captured_text": copied_text,
            "capture_method": method,
            "action": f"Captured {method} from '{title}'"
        }
    except Exception as e:
        logger.error(f"get_selected_or_page_text error: {e}")
        return {"success": False, "error": str(e)}

