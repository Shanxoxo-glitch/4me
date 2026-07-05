"""
Brian AI Assistant — Browser Agent
Login automation via Microsoft Edge (Playwright), credential management,
credential log deletion, and Spotify playback.
"""

import os
import json
import logging
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Persistent browser profile dir — stores cookies/sessions
PROFILE_DIR = Path(__file__).parent / "browser_profile"
CREDS_FILE  = Path(__file__).parent / "credentials.json"

# Active browser context registry (browser -> context)
# Note: Playwright sync API is not thread-safe, so we use a lock for synchronization
_active_contexts = {}
_playwright_instance = None
_playwright_lock = threading.Lock()

# ── Site URL mappings ─────────────────────────────────────────────────────────
SITE_URLS = {
    "google":    "https://accounts.google.com",
    "gmail":     "https://mail.google.com",
    "github":    "https://github.com/login",
    "spotify":   "https://accounts.spotify.com/login",
    "netflix":   "https://www.netflix.com/login",
    "youtube":   "https://accounts.google.com",
    "discord":   "https://discord.com/login",
    "twitter":   "https://twitter.com/login",
    "instagram": "https://www.instagram.com/accounts/login/",
    "reddit":    "https://www.reddit.com/login",
    "linkedin":  "https://www.linkedin.com/login",
    "twitch":    "https://www.twitch.tv/login",
}

# Sites that support Google OAuth
GOOGLE_SSO_SITES = {"github", "spotify", "discord", "reddit", "youtube", "twitch"}


# ── Credential Storage ────────────────────────────────────────────────────────

def _load_credentials(site: str) -> Optional[dict]:
    """Load stored credentials for a site from credentials.json."""
    if not CREDS_FILE.exists():
        return None
    try:
        with open(CREDS_FILE, "r") as f:
            all_creds = json.load(f)
        return all_creds.get(site.lower())
    except Exception as e:
        logger.error(f"Failed to load credentials: {e}")
        return None


def save_credentials(site: str, email: str, password: str) -> dict:
    """Save credentials for a site to credentials.json."""
    try:
        all_creds = {}
        if CREDS_FILE.exists():
            with open(CREDS_FILE, "r") as f:
                all_creds = json.load(f)

        all_creds[site.lower()] = {"email": email, "password": password}

        with open(CREDS_FILE, "w") as f:
            json.dump(all_creds, f, indent=2)

        logger.info(f"Credentials saved for: {site}")
        return {"success": True, "action": f"Credentials saved for {site}"}
    except Exception as e:
        logger.error(f"Failed to save credentials: {e}")
        return {"success": False, "error": str(e)}


def delete_credentials(site: str) -> dict:
    """
    Delete stored credentials for a specific site.
    Called when user says 'Brian, delete my GitHub login' or 'forget my Spotify credentials'.
    Also wipes the browser profile cache directory to clear cookies for that site.
    """
    try:
        if not CREDS_FILE.exists():
            return {"success": True, "action": f"No credentials were stored for {site}."}

        with open(CREDS_FILE, "r") as f:
            all_creds = json.load(f)

        site_key = site.lower()
        if site_key not in all_creds:
            return {"success": True, "action": f"No stored credentials found for {site}."}

        del all_creds[site_key]

        with open(CREDS_FILE, "w") as f:
            json.dump(all_creds, f, indent=2)

        logger.info(f"Credentials deleted for: {site}")

        # Optionally wipe the browser profile cache (removes site session cookies)
        _wipe_browser_cache_for_site(site_key)

        return {"success": True, "action": f"Credentials and session data for {site} have been deleted, sir."}
    except Exception as e:
        logger.error(f"Failed to delete credentials for {site}: {e}")
        return {"success": False, "error": str(e)}


def clear_all_credentials() -> dict:
    """
    Delete ALL stored credentials and wipe the browser profile entirely.
    Called when user says 'Brian, clear all stored logins' or 'delete all my credentials'.
    """
    try:
        deleted_sites = []

        if CREDS_FILE.exists():
            with open(CREDS_FILE, "r") as f:
                all_creds = json.load(f)
            deleted_sites = list(all_creds.keys())
            # Overwrite with empty
            with open(CREDS_FILE, "w") as f:
                json.dump({}, f, indent=2)

        # Wipe the entire browser profile directory (cookies, sessions)
        import shutil
        if PROFILE_DIR.exists():
            shutil.rmtree(PROFILE_DIR, ignore_errors=True)
            logger.info("Browser profile directory wiped.")

        logger.info("All credentials cleared.")
        sites_str = ", ".join(deleted_sites) if deleted_sites else "none"
        return {
            "success": True,
            "action": f"All credentials cleared, sir. Removed: {sites_str}. Browser sessions also wiped."
        }
    except Exception as e:
        logger.error(f"Failed to clear all credentials: {e}")
        return {"success": False, "error": str(e)}


def _wipe_browser_cache_for_site(site: str):
    """Best-effort: remove site-specific cache files from the browser profile."""
    try:
        import shutil
        # The Network folder contains cookies/cache in Chromium-based profiles
        network_dir = PROFILE_DIR / "Default" / "Network"
        if network_dir.exists():
            # We can't selectively wipe one site's cookies without a DB library,
            # so we wipe the entire Network cache (safe — it will rebuild on next login)
            shutil.rmtree(network_dir, ignore_errors=True)
            logger.info(f"Browser network cache cleared for site: {site}")
    except Exception as e:
        logger.debug(f"Browser cache wipe skipped: {e}")


def list_saved_logins() -> dict:
    """List all sites Brian has stored credentials for."""
    if not CREDS_FILE.exists():
        return {"success": True, "sites": [], "action": "No credentials stored yet"}
    try:
        with open(CREDS_FILE, "r") as f:
            all_creds = json.load(f)
        sites = list(all_creds.keys())
        return {"success": True, "sites": sites, "action": f"Stored logins: {', '.join(sites)}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Browser Login via Microsoft Edge ─────────────────────────────────────────

def browser_login(site: str, method: str = "auto", browser: str = "edge", skip_auto_login: bool = False, keep_open: bool = True) -> dict:
    """
    Open browser via Playwright and log into the requested site.
    Supports: edge, chrome, firefox, brave
    Uses channel to drive the real installed browser on Windows.
    A separate persistent profile is used so Brian's sessions don't mix with the user's.
    
    The persistent profile directory maintains cookies/sessions across calls, so users stay logged in.
    
    Args:
        site: Site/service to log into
        method: Login method ('google', 'direct', 'auto')
        browser: Browser to use ('edge', 'chrome', 'firefox', 'brave')
        skip_auto_login: If True, skip automatic login even if credentials are stored
        keep_open: If True, keep browser context open after login (default)
    """
    global _playwright_instance, _active_contexts
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "success": False,
            "error": "Playwright not installed. Run: pip install playwright && playwright install",
        }

    # Map browser names to Playwright channels
    browser_channels = {
        "edge": "msedge",
        "chrome": "chrome",
        "firefox": "firefox",
        "brave": "chrome",  # Brave uses Chromium, can be launched via chrome channel with executable path
    }

    browser_lower = browser.lower().strip()
    channel = browser_channels.get(browser_lower, "msedge")  # Default to Edge

    site_lower = site.lower().strip()
    login_url  = SITE_URLS.get(site_lower) or (
        site_lower if site_lower.startswith("http") else f"https://{site_lower}"
    )

    creds = _load_credentials(site_lower)

    if method == "auto":
        if skip_auto_login:
            method = "manual"
        elif creds:
            method = "direct"
        elif site_lower in GOOGLE_SSO_SITES:
            method = "google"
        else:
            method = "manual"

    logger.info(f"[browser_agent] Logging into '{site}' via method='{method}', url={login_url} [Browser: {browser}]")

    PROFILE_DIR.mkdir(exist_ok=True)

    try:
        # Use lock to ensure thread-safe access to Playwright instance
        with _playwright_lock:
            # Initialize Playwright instance if not exists (keep it alive)
            if _playwright_instance is None:
                _playwright_instance = sync_playwright().start()
                logger.info("[browser_agent] Playwright instance initialized and kept alive")
            
            p = _playwright_instance
        
        # Check if we have an active context for this browser
        context_key = f"{browser_lower}_context"
        context = _active_contexts.get(context_key)
        
        if context:
            logger.info(f"[browser_agent] Reusing existing {browser} context")
            # Check if context is still valid by trying to get pages
            try:
                pages = context.pages
                if not pages:
                    # No pages, create a new one
                    page = context.new_page()
                else:
                    # Use existing page or create new tab
                    page = context.new_page()
            except Exception as e:
                logger.warning(f"[browser_agent] Existing context invalid, creating new: {e}")
                context = None
                _active_contexts.pop(context_key, None)
        
        if not context:
            # Launch the specified browser with minimal parameters to avoid crashes
            launch_kwargs = {
                "headless": False,
            }

            # For Brave, we need to specify the executable path
            if browser_lower == "brave":
                import shutil
                brave_path = shutil.which("brave.exe") or shutil.which("brave")
                if brave_path:
                    launch_kwargs["executable_path"] = brave_path
                    launch_kwargs["channel"] = None
                else:
                    # Try common Brave installation paths
                    from pathlib import Path
                    possible_paths = [
                        Path("C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe"),
                        Path("C:/Program Files (x86)/BraveSoftware/Brave-Browser/Application/brave.exe"),
                    ]
                    for path in possible_paths:
                        if path.exists():
                            launch_kwargs["executable_path"] = str(path)
                            launch_kwargs["channel"] = None
                            break
                    else:
                        return {
                            "success": False,
                            "error": "Brave browser not found. Please install Brave or specify a different browser.",
                        }
                # Use a separate profile directory for Brave to avoid permission conflicts
                brave_profile_dir = PROFILE_DIR / "brave_profile"
                brave_profile_dir.mkdir(exist_ok=True)
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(brave_profile_dir),
                    **launch_kwargs
                )
            else:
                launch_kwargs["channel"] = channel
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(PROFILE_DIR),
                    **launch_kwargs
                )
            _active_contexts[context_key] = context
            logger.info(f"[browser_agent] Created new {browser} context")
            page = context.new_page()
        else:
            page = context.new_page()
        
        page.goto(login_url, wait_until="domcontentloaded", timeout=30000)

        current_url = page.url
        if "login" not in current_url and "signin" not in current_url and "accounts" not in current_url:
            logger.info(f"[browser_agent] Already logged in at {current_url}")
            # Don't close context - keep it open for reuse
            return {"success": True, "action": f"Already logged in to {site}. {browser.capitalize()} opened.", "url": current_url}

        result_action = f"Opened login page for {site} in {browser.capitalize()}"

        if method == "google":
            google_selectors = [
                "text=Sign in with Google", "text=Continue with Google",
                "text=Log in with Google", "[data-provider='google']",
                "a[href*='google']", "button:has-text('Google')",
            ]
            clicked = False
            for sel in google_selectors:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                result_action = f"Login page for {site} opened in {browser.capitalize()}. Please click 'Sign in with Google' manually."
            else:
                google_creds = _load_credentials("google")
                if google_creds and not skip_auto_login:
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                    _fill_google_login(page, google_creds)
                    result_action = f"Google login initiated for {site} in {browser.capitalize()}."
                else:
                    result_action = f"Google OAuth opened for {site} in {browser.capitalize()}. Please complete login manually."
            page.wait_for_timeout(3000)

        elif method == "direct" and creds and not skip_auto_login:
            page.wait_for_load_state("domcontentloaded")
            filled = _fill_login_form(page, creds["email"], creds["password"], site_lower)
            result_action = (
                f"Logged into {site} in {browser.capitalize()} with stored credentials."
                if filled else
                f"Login page for {site} opened in {browser.capitalize()} — please complete login manually."
            )

        else:
            result_action = (
                f"Login page for {site} opened in {browser.capitalize()}. "
                f"No credentials stored — log in manually or say 'remember my {site} login'."
            )

        # Never close context when keep_open=True (default) to allow reuse
        if not keep_open:
            context.close()
            _active_contexts.pop(context_key, None)
        else:
            logger.info(f"[browser_agent] Keeping {browser.capitalize()} context open for continued use.")
        
        return {"success": True, "action": result_action, "site": site, "url": login_url, "kept_open": keep_open}

    except Exception as e:
        logger.error(f"[browser_agent] browser_login error: {e}")
        return {"success": False, "error": str(e), "site": site}


def _fill_google_login(page, creds: dict):
    try:
        page.wait_for_selector('input[type="email"]', timeout=8000)
        page.fill('input[type="email"]', creds["email"])
        page.keyboard.press("Enter")
        page.wait_for_timeout(1500)
        page.wait_for_selector('input[type="password"]', timeout=8000)
        page.fill('input[type="password"]', creds["password"])
        page.keyboard.press("Enter")
        page.wait_for_timeout(3000)
    except Exception as e:
        logger.warning(f"[browser_agent] Google login form fill failed: {e}")


def _fill_login_form(page, email: str, password: str, site: str) -> bool:
    email_selectors = [
        'input[type="email"]', 'input[name="email"]', 'input[name="username"]',
        'input[name="user"]', 'input[id="email"]', 'input[id="username"]',
        'input[placeholder*="email" i]', 'input[placeholder*="username" i]',
        'input[autocomplete="email"]', 'input[autocomplete="username"]',
    ]
    pw_selectors = [
        'input[type="password"]', 'input[name="password"]', 'input[id="password"]',
    ]
    submit_selectors = [
        'button[type="submit"]', 'input[type="submit"]',
        'button:has-text("Log in")', 'button:has-text("Sign in")',
        'button:has-text("Login")', 'button:has-text("Continue")', 'button:has-text("Next")',
    ]
    try:
        page.wait_for_load_state("domcontentloaded", timeout=8000)
        email_filled = False
        for sel in email_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=1000):
                    el.click()
                    el.fill(email)
                    email_filled = True
                    break
            except Exception:
                continue
        if not email_filled:
            return False

        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=1000):
                    pw_visible = page.locator(pw_selectors[0]).is_visible()
                    if not pw_visible and any(w in (btn.text_content() or "").lower() for w in ["next", "continue"]):
                        btn.click()
                        page.wait_for_timeout(1500)
                        break
            except Exception:
                continue

        pw_filled = False
        for sel in pw_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=3000):
                    el.click()
                    el.fill(password)
                    pw_filled = True
                    break
            except Exception:
                continue
        if not pw_filled:
            return False

        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=1000):
                    btn.click()
                    page.wait_for_timeout(3000)
                    return True
            except Exception:
                continue

        page.keyboard.press("Enter")
        page.wait_for_timeout(3000)
        return True
    except Exception as e:
        logger.error(f"[browser_agent] _fill_login_form error: {e}")
        return False


def remember_credentials(site: str, email: str, password: str) -> dict:
    """Called when user says 'remember my X login'."""
    return save_credentials(site, email, password)


def play_spotify_song(query: str) -> dict:
    """Open Spotify Web Player in Edge/default browser."""
    import webbrowser
    import urllib.parse
    import time
    import pyautogui
    import threading

    encoded_query = urllib.parse.quote(query)
    search_url = f"https://open.spotify.com/search/{encoded_query}"
    logger.info(f"[spotify_playback] Opening: {search_url}")
    webbrowser.open(search_url)

    def _play_sequence():
        try:
            time.sleep(5.0)
            for _ in range(6):
                pyautogui.press("tab")
                time.sleep(0.1)
            pyautogui.press("space")
        except Exception as e:
            logger.error(f"[spotify_playback] Play sequence error: {e}")

    threading.Thread(target=_play_sequence, daemon=True).start()
    return {"success": True, "action": f"Opened Spotify search for '{query}' in Edge."}
