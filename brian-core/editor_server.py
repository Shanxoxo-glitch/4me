"""
Brian AI Assistant — Standalone IDE Backend Server
Serves the Monaco workspace files, executes terminal processes,
and handles AI instructions specifically formatted for coding/editing.
"""

import asyncio
import json
import logging
import os
import sys
import subprocess
import threading
from pathlib import Path
import httpx

import time

# Load env variables
from dotenv import load_dotenv
ENV_PATH = Path(__file__).parent.parent / "deployment.env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BrianEditorServer")

import websockets

PORT = 9002
WORKSPACE_DIR = Path(__file__).parent.parent.resolve()

CONVERSATIONS_DIR = Path(__file__).parent / "conversations"
CONVERSATIONS_DIR.mkdir(exist_ok=True)

OPENROUTER_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENROUTER_BASE    = "https://openrouter.ai/api/v1"

# Ordered coding model fallback chain — all free tier via OpenRouter
CODING_MODELS = [
    "cohere/north-mini-code:free",
    "poolside/laguna-m.1:free",
    "poolside/laguna-xs.2:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]

# Excluded folders in scan
EXCLUDED_DIRS = {".git", "venv", "node_modules", "__pycache__", ".agents", ".gemini", "figures"}

# ─────────────────────────────────────────────
# WORKSPACE SCANNER
# ─────────────────────────────────────────────
def scan_workspace(base_dir: Path, max_depth: int = 4) -> list[dict]:
    """Recursively scan files and folders under base_dir."""
    results = []
    
    def walk(curr_dir: Path, depth: int):
        if depth > max_depth:
            return
        try:
            for entry in sorted(curr_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                if entry.name in EXCLUDED_DIRS:
                    continue
                    
                rel_path = entry.relative_to(base_dir).as_posix()
                results.append({
                    "name": entry.name,
                    "path": rel_path,
                    "type": "folder" if entry.is_dir() else "file",
                    "depth": depth
                })
                
                if entry.is_dir():
                    walk(entry, depth + 1)
        except PermissionError:
            pass

    walk(base_dir, 1)
    return results

# ─────────────────────────────────────────────
# INTERACTIVE TERMINAL PROCESS
# ─────────────────────────────────────────────
class TerminalSession:
    """Manages an active PowerShell process linked to the Monaco terminal."""
    def __init__(self, ws_conn):
        self.ws = ws_conn
        self.process = None
        self.read_thread = None
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.get_event_loop()

    def start(self):
        # Open PowerShell on Windows
        self.process = subprocess.Popen(
            ["powershell.exe", "-NoLogo"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=0
        )
        self.read_thread = threading.Thread(target=self._read_output, daemon=True)
        self.read_thread.start()

    def write(self, data: str):
        if self.process and self.process.stdin:
            self.process.stdin.write(data)
            self.process.stdin.flush()

    def _read_output(self):
        while self.process:
            try:
                char = self.process.stdout.read(1)
                if not char:
                    break
                # Send to frontend
                asyncio.run_coroutine_threadsafe(
                    self.ws.send(json.dumps({
                        "type": "run_output",
                        "output": char
                    })),
                    self.loop
                )
            except Exception as e:
                logger.error(f"Terminal read error: {e}")
                break

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process = None

# ─────────────────────────────────────────────
# AI CODE EDITOR CONTROLLER
# ─────────────────────────────────────────────
async def handle_ai_coding(instruction: str, active_file: str, selected_code: str) -> dict:
    """Uses OpenRouter to generate clean code modifications based on selection & files."""
    file_content = ""
    full_path = WORKSPACE_DIR / active_file if active_file else None
    
    if full_path and full_path.exists():
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        except Exception as e:
            file_content = f"Error reading file: {e}"

    system_prompt = """You are BRIAN — the advanced Jarvis-like assistant integrated directly inside the code editor.
Your goal is to edit, write, or refactor code for the user.

RULES:
1. Always output the entire updated code block in your response using a Markdown code fence.
2. Ensure there are NO placeholders (like '// rest of code stays the same'). Output the FULL file content or full updated function.
3. Be direct and precise. After the code block, explain what changes you made in 1-2 bullet points.
4. If modifying selected code specifically, target your edits to that segment but output the resulting full code.
"""

    user_content = f"Active File: {active_file}\n"
    if selected_code:
        user_content += f"Selected Code Segment:\n```\n{selected_code}\n```\n"
    if file_content:
        user_content += f"Full File Content:\n```\n{file_content}\n```\n"
        
    user_content += f"Instruction: {instruction}"

    async with httpx.AsyncClient(timeout=120.0) as client:
        last_error = None
        for model in CODING_MODELS:
            try:
                resp = await client.post(
                    f"{OPENROUTER_BASE}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "HTTP-Referer": "http://localhost:9002",
                        "X-Title": "Brian Code Editor",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content}
                        ],
                        "temperature": 0.2,
                        "max_tokens": 4096,
                    }
                )
                if resp.status_code == 200:
                    logger.info(f"[editor] AI coding succeeded with model: {model}")
                    data  = resp.json()
                    reply = data["choices"][0]["message"]["content"]

                    # Extract code block from response
                    code_block  = ""
                    explanation = reply

                    if "```" in reply:
                        parts = reply.split("```")
                        for i, part in enumerate(parts):
                            if i % 2 == 1:
                                lines = part.split("\n")
                                if lines and lines[0].strip().isalpha():
                                    lines = lines[1:]
                                code_block  = "\n".join(lines).strip()
                                explanation = "\n".join(parts[i+1:]).strip()
                                break

                    if code_block:
                        return {
                            "type":        "ai_edit",
                            "path":        active_file,
                            "content":     code_block,
                            "explanation": explanation or "I have updated the code according to your instructions, sir.",
                            "model":       model,
                        }
                    else:
                        return {
                            "type":  "chat_response",
                            "text":  reply,
                            "model": model,
                        }

                logger.warning(f"[editor] Model {model} returned HTTP {resp.status_code} — trying next")
                last_error = f"HTTP {resp.status_code}"
            except Exception as e:
                logger.warning(f"[editor] Model {model} error: {e} — trying next")
                last_error = str(e)

        return {
            "type": "chat_response",
            "text": f"Apologies, sir. All coding models are currently unavailable: {last_error}"
        }


# ─────────────────────────────────────────────
# WEBSOCKET ROUTER
# ─────────────────────────────────────────────
async def handle_connection(ws):
    global WORKSPACE_DIR
    logger.info("Editor frontend connected.")
    term_session = TerminalSession(ws)
    term_session.start()
    
    try:
        async for raw_msg in ws:
            try:
                msg = json.loads(raw_msg)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")
            
            if msg_type == "scan_workspace":
                files = scan_workspace(WORKSPACE_DIR)
                await ws.send(json.dumps({
                    "type": "workspace_structure",
                    "files": files
                }))
                
            elif msg_type == "read_file":
                file_path = WORKSPACE_DIR / msg["path"]
                if file_path.exists() and file_path.is_file():
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    await ws.send(json.dumps({
                        "type": "file_content",
                        "path": msg["path"],
                        "content": content
                    }))
                    
            elif msg_type == "save_file":
                file_path = WORKSPACE_DIR / msg["path"]
                os.makedirs(file_path.parent, exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(msg["content"])
                await ws.send(json.dumps({
                    "type": "save_success",
                    "path": msg["path"]
                }))
                
            elif msg_type == "change_workspace":
                new_path = Path(msg["path"]).resolve()
                if new_path.exists() and new_path.is_dir():
                    WORKSPACE_DIR = new_path
                    files = scan_workspace(WORKSPACE_DIR)
                    await ws.send(json.dumps({
                        "type": "workspace_structure",
                        "files": files,
                        "workspace_name": WORKSPACE_DIR.name
                    }))
                    logger.info(f"Workspace changed to: {WORKSPACE_DIR}")
                else:
                    await ws.send(json.dumps({
                        "type": "chat_response",
                        "text": f"Error: Path '{msg['path']}' does not exist or is not a directory."
                    }))

            elif msg_type == "get_sessions":
                sessions = []
                for p in CONVERSATIONS_DIR.glob("*.json"):
                    try:
                        with open(p, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        sessions.append({
                            "id": data.get("id"),
                            "title": data.get("title", "Untitled Chat"),
                            "timestamp": data.get("timestamp", 0)
                        })
                    except Exception:
                        pass
                sessions.sort(key=lambda x: x["timestamp"], reverse=True)
                await ws.send(json.dumps({
                    "type": "sessions_list",
                    "sessions": sessions
                }))

            elif msg_type == "load_session":
                session_id = msg["session_id"]
                path = CONVERSATIONS_DIR / f"{session_id}.json"
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    await ws.send(json.dumps({
                        "type": "session_loaded",
                        "session_id": session_id,
                        "messages": data.get("messages", [])
                    }))

            elif msg_type == "save_session_message":
                session_id = msg["session_id"]
                save_session_message_internal(session_id, msg["message"])

            elif msg_type == "chat_instruction":
                # Start AI request asynchronously to not block WS connection
                asyncio.create_task(
                    process_and_reply_ai(
                        ws, 
                        msg["text"], 
                        msg.get("active_file"), 
                        msg.get("selected_code"),
                        msg.get("session_id")
                    )
                )
                
            elif msg_type == "run_file":
                file_path = WORKSPACE_DIR / msg["path"]
                # Run the Python code inside our active virtualenv
                py_path = WORKSPACE_DIR / "brian-core" / "venv" / "Scripts" / "python.exe"
                if not py_path.exists():
                    py_path = sys.executable  # fallback

                term_session.write(f'& "{py_path}" "{file_path}"\r\n')
                
            elif msg_type == "terminal_input":
                term_session.write(msg["data"])

    except websockets.exceptions.ConnectionClosed:
        logger.info("Editor disconnected.")
    finally:
        term_session.stop()

def save_session_message_internal(session_id: str, message: dict):
    path = CONVERSATIONS_DIR / f"{session_id}.json"
    data = {"id": session_id, "title": "Untitled Chat", "timestamp": time.time(), "messages": []}
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    
    # Append message if not duplicate
    exists = any(m.get("text") == message.get("text") and m.get("role") == message.get("role") and m.get("timestamp") == message.get("timestamp") for m in data.get("messages", []))
    if not exists:
        data["messages"].append(message)
        
    # Generate title from first user message
    if data.get("title") == "Untitled Chat" and message.get("role") == "user":
        first_msg = message.get("text", "")
        data["title"] = first_msg[:30] + ("..." if len(first_msg) > 30 else "")
        
    data["timestamp"] = time.time()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save session message: {e}")

async def process_and_reply_ai(ws, instruction: str, active_file: str, selected_code: str, session_id: str = None):
    if session_id:
        save_session_message_internal(session_id, {
            "role": "user",
            "text": instruction,
            "timestamp": time.time()
        })
    response = await handle_ai_coding(instruction, active_file, selected_code)
    if session_id:
        text_resp = response.get("explanation") if response.get("type") == "ai_edit" else response.get("text")
        if text_resp:
            save_session_message_internal(session_id, {
                "role": "brian",
                "text": text_resp,
                "model": response.get("model", "cohere/north-mini-code:free"),
                "timestamp": time.time()
            })
    await ws.send(json.dumps(response))

# ─────────────────────────────────────────────
# RUN HTTP SERVER FOR STATIC FILES
# ─────────────────────────────────────────────
HTTP_PORT = 9003
EDITOR_HTML_DIR = Path(__file__).parent.parent / "brian-editor"

def run_http_server():
    from http.server import SimpleHTTPRequestHandler, HTTPServer
    class QuietHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(EDITOR_HTML_DIR), **kwargs)
        def log_message(self, format, *args):
            pass  # suppress access logs

    server = HTTPServer(("localhost", HTTP_PORT), QuietHandler)
    logger.info(f"Brian Standalone IDE HTTP Server running on http://localhost:{HTTP_PORT}")
    server.serve_forever()

# ─────────────────────────────────────────────
# RUN SERVER
# ─────────────────────────────────────────────
async def main():
    # Start HTTP server in a daemon thread
    http_thread = threading.Thread(target=run_http_server, daemon=True, name="Editor-HTTP")
    http_thread.start()

    logger.info(f"Starting Brian IDE Backend Server on ws://localhost:{PORT}")
    async with websockets.serve(handle_connection, "localhost", PORT):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
