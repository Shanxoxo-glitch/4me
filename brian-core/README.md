# BRIAN — Your Jarvis-Like AI Desktop Assistant

> *"All systems online, sir."*

BRIAN is a fully autonomous, always-on AI desktop assistant. Say **"Hey Brian"** and he listens, thinks, speaks back, and takes real action on your computer — no keyboard needed.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🎙️ Wake Word | Always-on "Hey Brian" detection via openWakeWord |
| 🗣️ Voice I/O | Whisper STT + ElevenLabs Jarvis-like voice |
| 🧠 AI Brain | Claude 3.5 Sonnet via OpenRouter with full memory |
| 💻 System Control | Open apps, folders, websites, type text, screenshots |
| 🌐 Internet | Real-time web search via DuckDuckGo |
| 😄 Emotions | 8 emotional states that change Brian's personality & voice |
| 🖥️ HUD | Animated glassmorphism floating widget |
| 🚀 Auto-start | Launches automatically with Windows |

---

## 🚀 Quick Start

### Step 1: Install (one-time)
```
Double-click: install.bat
```

### Step 2: Run Brian
```
Double-click: start_brian.bat
```

### Step 3: Say "Hey Brian"!

---

## 📁 Project Structure

```
brian-core/
├── main.py              ← Entry point & orchestrator
├── wake_word.py         ← openWakeWord "Hey Brian" detection
├── audio_pipeline.py    ← Mic capture + Whisper STT
├── brain.py             ← LLM + agentic tool-calling loop
├── tts.py               ← ElevenLabs TTS engine
├── emotion_engine.py    ← 8-state emotion detection
├── system_control.py    ← Windows OS control tools
├── hud_server.py        ← WebSocket + HTTP server for HUD
├── install_startup.py   ← Windows registry auto-start
├── requirements.txt     ← Python dependencies
├── install.bat          ← One-click installer
├── start_brian.bat      ← Manual launcher
└── .env                 ← API keys & config

brian-hud/
├── index.html           ← Jarvis-style HUD UI
├── style.css            ← Glassmorphism animations
└── brian.js             ← WebSocket real-time updates

openWakeWord/            ← Wake word engine (cloned from GitHub)
```

---

## 🗣️ Example Voice Commands

| Say this... | Brian does this... |
|---|---|
| "Hey Brian, open YouTube" | Opens YouTube in browser |
| "Hey Brian, open my Downloads folder" | Opens Downloads in Explorer |
| "Hey Brian, search latest AI news" | Searches web, reads summary |
| "Hey Brian, open VS Code" | Launches VS Code |
| "Hey Brian, set volume to 50" | Sets system volume to 50% |
| "Hey Brian, take a screenshot" | Captures screen |
| "Hey Brian, what's the weather in Mumbai?" | Searches and reads weather |
| "Hey Brian, close Spotify" | Kills Spotify process |
| "Hey Brian, lock my screen" | Locks Windows |
| "Hey Brian, write an email to John saying..." | Types the email for you |

---

## ⚙️ Configuration (`.env`)

```env
OPENAI_API_KEY=your_openrouter_key
BRIAN_MODEL=anthropic/claude-3.5-sonnet
ELEVENLABS_API_KEY=your_elevenlabs_key
TTS_VOICE_ID=pNInz6obpgDQGcFmaJgB
WHISPER_MODEL=base
WAKE_THRESHOLD=0.5
```

---

## 🎤 Changing Brian's Voice

1. Visit [ElevenLabs Voice Lab](https://elevenlabs.io/app/voice-lab)
2. Pick or clone a voice
3. Copy the Voice ID
4. Set `TTS_VOICE_ID=<your_id>` in `.env`

---

## 🔧 Adjusting Wake Word Sensitivity

In `.env`:
- `WAKE_THRESHOLD=0.3` — more sensitive (may have false triggers)
- `WAKE_THRESHOLD=0.7` — less sensitive (requires clearer pronunciation)

---

## 🛑 Removing Auto-start

```powershell
cd brian-core
python install_startup.py --uninstall
```
