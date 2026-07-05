"""
Brian AI Assistant — Universal Screen Code Agent (Tier 2)
Provides tools for screen OCR, clipboard-based code editing,
and reviewing/modifying code in any editor.

Coding fallback model chain (OpenRouter, all free):
  1. cohere/north-mini-code:free
  2. poolside/laguna-m.1:free
  3. poolside/laguna-xs.2:free
  4. nvidia/nemotron-3-super-120b-a12b:free
"""

import time
import logging
import pyautogui
import pyperclip
import pygetwindow as gw
import httpx
import os

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENROUTER_BASE    = "https://openrouter.ai/api/v1"

# Ordered fallback chain for code generation tasks
CODING_MODELS = [
    "cohere/north-mini-code:free",
    "poolside/laguna-m.1:free",
    "poolside/laguna-xs.2:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]


def _openrouter_coding_call(messages: list, temperature: float = 0.1) -> str:
    """
    Call OpenRouter with the coding fallback chain.
    Tries each model in order until one succeeds.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer":  "http://localhost:3000",
        "X-Title":       "Brian Code Agent",
        "Content-Type":  "application/json",
    }
    with httpx.Client(timeout=90.0) as client:
        for model in CODING_MODELS:
            try:
                resp = client.post(
                    f"{OPENROUTER_BASE}/chat/completions",
                    headers=headers,
                    json={
                        "model":       model,
                        "messages":    messages,
                        "temperature": temperature,
                        "max_tokens":  4096,
                    },
                )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"].strip()
                    logger.info(f"[code_agent] Succeeded with model: {model}")
                    return content
                logger.warning(f"[code_agent] {model} returned HTTP {resp.status_code} — trying next")
            except Exception as e:
                logger.warning(f"[code_agent] {model} error: {e} — trying next")

    raise RuntimeError("All coding models failed. OpenRouter may be unavailable.")


class CodeAgent:
    """
    Agent responsible for universal screen-level code operations:
    1. Grabbing code via clipboard copies (Ctrl+C).
    2. Editing code and pasting back (Ctrl+V).
    3. Reviewing code and explaining in natural language.
    """

    def __init__(self):
        logger.info("Universal CodeAgent initialized (coding fallback chain active).")

    def get_selected_code(self) -> str:
        """Trigger Ctrl+C in the active window and return clipboard content."""
        try:
            pyperclip.copy("")
            pyautogui.hotkey("ctrl", "c")
            time.sleep(0.3)
            return pyperclip.paste().strip()
        except Exception as e:
            logger.error(f"Failed to get selected code: {e}")
            return ""

    def replace_selected_code(self, new_code: str):
        """Copy new_code to clipboard and Ctrl+V it into the active window."""
        try:
            pyperclip.copy(new_code)
            time.sleep(0.1)
            pyautogui.hotkey("ctrl", "v")
            logger.info("Successfully pasted modified code back to active window.")
        except Exception as e:
            logger.error(f"Failed to replace selected code: {e}")

    async def execute_voice_edit(self, instruction: str) -> dict:
        """
        Full edit loop:
        1. Grab selected text.
        2. Feed to coding LLM (fallback chain).
        3. Paste result back.
        """
        code = self.get_selected_code()
        if not code:
            return {
                "success": False,
                "error":   "No code selected. Please select the code you wish me to edit, sir.",
            }

        active_win = gw.getActiveWindow()
        win_title  = active_win.title if active_win else "Editor"

        system_prompt = f"""You are BRIAN — a Jarvis-like senior coding AI integrated directly in the editor (Window: {win_title}).
You are given a selected block of code and an instruction.

RULES:
1. Modify the code exactly as instructed.
2. Return ONLY the raw, corrected code. NO markdown fences. NO explanation. NO placeholders.
3. Preserve original formatting, indentation, and whitespace exactly.
"""
        try:
            modified_code = _openrouter_coding_call([
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": f"Selected Code:\n{code}\n\nInstruction: {instruction}"},
            ], temperature=0.1)

            # Strip markdown fences if model ignored instructions
            if modified_code.startswith("```"):
                lines = modified_code.split("\n")
                lines = lines[1:] if lines[0].startswith("```") else lines
                lines = lines[:-1] if lines and lines[-1].startswith("```") else lines
                modified_code = "\n".join(lines).strip()

            self.replace_selected_code(modified_code)
            return {"success": True, "action": f"Edited selected code in {win_title}."}
        except Exception as e:
            logger.error(f"Code edit failed: {e}")
            return {"success": False, "error": f"Apologies, sir — coding subsystems unavailable: {e}"}

    async def review_active_code(self) -> str:
        """Read selected code, review it, return a natural-language explanation."""
        code = self.get_selected_code()
        if not code:
            return "Please select the code you want me to review, sir."

        system_prompt = """You are BRIAN — a Jarvis-like senior software architect.
Review the selected code concisely:
1. Any logic bugs or security issues.
2. Performance improvements worth noting.
3. Clean code / readability suggestions.

Keep your response to 2-3 bullet points. Start with a brief JARVIS-style confirmation."""
        try:
            return _openrouter_coding_call([
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": f"Code:\n{code}"},
            ], temperature=0.3)
        except Exception as e:
            return f"Apologies, sir — I encountered an error during review: {e}"
