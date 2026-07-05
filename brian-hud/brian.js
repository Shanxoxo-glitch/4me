/**
 * BRIAN HUD — Real-time WebSocket Client
 * Connects to the Python backend and updates the UI live.
 */

const WS_URL = 'ws://localhost:9000';

// ── DOM refs ─────────────────────────────────────────────
const orbSection   = document.querySelector('.orb-section');
const stateText    = document.getElementById('state-text');
const stateDot     = document.getElementById('state-dot');
const transcript   = document.getElementById('transcript');
const actionLog    = document.getElementById('action-log');
const waveContainer= document.getElementById('wave-container');
const infoTime     = document.getElementById('info-time');
const infoStatus   = document.getElementById('info-status');
const emotionChips = document.querySelectorAll('.chip');
const btnMinimize  = document.getElementById('btn-minimize');

// ── State ─────────────────────────────────────────────────
let currentState   = 'idle';
let reconnectTimer = null;
let ws             = null;

// ── Clock ─────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  infoTime.textContent = now.toLocaleTimeString('en-US', {
    hour: '2-digit', minute: '2-digit', hour12: false
  });
}
setInterval(updateClock, 1000);
updateClock();

// ── WebSocket ─────────────────────────────────────────────
function connect() {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    console.log('BRIAN HUD connected.');
    infoStatus.textContent = 'ONLINE';
    infoStatus.style.color = '#69F0AE';
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleMessage(msg);
    } catch(e) {
      console.warn('Invalid WS message:', event.data);
    }
  };

  ws.onclose = () => {
    console.warn('BRIAN WS disconnected. Reconnecting in 3s...');
    infoStatus.textContent = 'RECONNECTING';
    infoStatus.style.color = '#FFD54F';
    reconnectTimer = setTimeout(connect, 3000);
  };

  ws.onerror = (e) => {
    console.error('WS error:', e);
    ws.close();
  };
}

// ── Message Handler ────────────────────────────────────────
function handleMessage(msg) {
  switch(msg.type) {
    case 'state':
      applyState(msg.state, msg.emotion);
      break;
    case 'transcript':
      addTranscript(msg.text, msg.role, msg.emotion);
      break;
    case 'action':
      addAction(msg.action);
      break;
    default:
      console.log('Unknown message type:', msg.type);
  }
}

// ── State Renderer ─────────────────────────────────────────
function applyState(state, emotion) {
  currentState = state;

  // Update body class for CSS variable overrides
  document.body.className = `state-${state}`;

  // Update orb animation class
  orbSection.classList.remove('listening', 'speaking', 'processing', 'idle');
  if (state === 'listening' || state === 'speaking') {
    orbSection.classList.add(state);
  }

  // State badge text
  const labels = {
    idle:       'STANDBY',
    listening:  'LISTENING...',
    processing: 'PROCESSING...',
    speaking:   'SPEAKING',
    error:      'ERROR',
  };
  stateText.textContent = labels[state] || state.toUpperCase();

  // Wave visualizer
  const showWave = state === 'listening' || state === 'speaking';
  waveContainer.classList.toggle('active', showWave);

  // Apply emotion
  if (emotion) applyEmotion(emotion);
}

// ── Emotion Renderer ───────────────────────────────────────
function applyEmotion(emotion) {
  emotionChips.forEach(chip => {
    chip.classList.toggle('active', chip.dataset.emotion === emotion.name);
  });
}

// ── Transcript ─────────────────────────────────────────────
function addTranscript(text, role, emotion) {
  if (!text) return;

  const item = document.createElement('div');
  item.className = `transcript-item ${role}`;

  const roleLabel = role === 'brian' ? 'BRIAN' : 'YOU';
  item.innerHTML = `
    <span class="t-role">${roleLabel}</span>
    <p>${escapeHtml(text)}</p>
  `;

  transcript.appendChild(item);

  // Keep max 20 items
  while (transcript.children.length > 20) {
    transcript.removeChild(transcript.firstChild);
  }

  // Scroll to bottom
  transcript.scrollTop = transcript.scrollHeight;
}

// ── Action Log ─────────────────────────────────────────────
const ACTION_ICONS = {
  'Opened':     '🚀',
  'Searched':   '🔍',
  'Typed':      '⌨️',
  'Screenshot': '📸',
  'Volume':     '🔊',
  'Closed':     '✖️',
  'Ran':        '⚡',
  'Locked':     '🔒',
  'default':    '◆',
};

function getActionIcon(action) {
  for (const [key, icon] of Object.entries(ACTION_ICONS)) {
    if (action.toLowerCase().includes(key.toLowerCase())) return icon;
  }
  return ACTION_ICONS.default;
}

function addAction(actionText) {
  const item = document.createElement('div');
  item.className = 'action-item';
  item.innerHTML = `
    <span class="action-icon">${getActionIcon(actionText)}</span>
    <span class="action-text">${escapeHtml(actionText)}</span>
  `;

  actionLog.appendChild(item);

  // Keep max 10 actions
  while (actionLog.children.length > 10) {
    actionLog.removeChild(actionLog.firstChild);
  }

  actionLog.scrollTop = actionLog.scrollHeight;
}

// ── Utils ──────────────────────────────────────────────────
function escapeHtml(text) {
  const d = document.createElement('div');
  d.appendChild(document.createTextNode(text));
  return d.innerHTML;
}

// ── Window Controls ────────────────────────────────────────
btnMinimize.addEventListener('click', () => {
  // For pywebview — minimize via window.pywebview if available
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.minimize();
  } else {
    // In browser: just hide for demo
    document.body.style.opacity = '0.3';
    setTimeout(() => document.body.style.opacity = '1', 2000);
  }
});

// ── Boot splash animation ──────────────────────────────────
(function bootSequence() {
  const items = ['NEURAL ENGINE', 'VOICE PIPELINE', 'AGENT CORE', 'SYSTEM CONTROL'];
  let i = 0;
  function next() {
    if (i < items.length) {
      addAction(`Initializing ${items[i++]}...`);
      setTimeout(next, 500);
    } else {
      // Clear and show ready
      setTimeout(() => {
        actionLog.innerHTML = '';
        addAction('BRIAN online — all systems nominal');
      }, 600);
    }
  }
  setTimeout(next, 800);
})();

// ── Start WS connection ─────────────────────────────────────
connect();

// ── Keyboard shortcut: Esc to dismiss ──────────────────────
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.body.style.transition = 'opacity 0.3s';
    document.body.style.opacity = '0.2';
    setTimeout(() => {
      document.body.style.opacity = '1';
    }, 3000);
  }
});
