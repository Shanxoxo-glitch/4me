/**
 * BRIAN COGNITIVE IDE — Dynamic Editor Controller
 * Full VS Code-like behaviour: file tree, multi-tab, Monaco, terminal,
 * AI co-pilot chat with coding model fallback, command palette, context menu.
 */

'use strict';

// ═══════════════════════════════════════════════════════
// CONFIG
// ═══════════════════════════════════════════════════════
const WS_PORT     = 9002;
const WS_URL      = `ws://localhost:${WS_PORT}`;
const CODING_MODELS = [
  'cohere/north-mini-code:free',
  'poolside/laguna-m.1:free',
  'poolside/laguna-xs.2:free',
  'nvidia/nemotron-3-super-120b-a12b:free',
];

// ═══════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════
let editor        = null;    // Monaco editor instance
let monacoLoaded  = false;
let ws            = null;
let wsReady       = false;
let reconnectTimer = null;

// Tab management
const tabModels   = {};      // path → Monaco ITextModel
const tabDirty    = {};      // path → boolean (modified)
let openTabs      = [];      // ordered list of open paths
let activeTab     = null;    // currently focused tab path

// Workspace
let workspaceFiles = [];     // flat list of file/folder objects from backend
let treeState      = {};     // folder path → open/closed

// Current suggestion
let currentSuggestion = null;

// Session ID
let activeSessionId = generateSessionId();

function generateSessionId() {
  return 'chat_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7);
}

// Context menu target
let contextMenuTarget = null;

// Command palette
let cpIndex = -1;

// Sidebar resizer
let sidebarResizing = false;

// Bottom panel resize
let panelResizing = false;
let panelStartY   = 0;
let panelStartH   = 0;

// ═══════════════════════════════════════════════════════
// DOM REFS
// ═══════════════════════════════════════════════════════
const dom = {
  splash:          document.getElementById('splash'),
  monacoContainer: document.getElementById('monaco-container'),
  tabsBar:         document.getElementById('tabs-bar'),
  noTabsHint:      document.getElementById('no-tabs-hint'),
  breadcrumb:      document.getElementById('breadcrumb'),
  fileTree:        document.getElementById('file-tree'),
  workspaceName:   document.getElementById('workspace-name'),
  activeFileLabel: document.getElementById('active-file-label'),
  wsBadge:         document.getElementById('ws-badge'),
  wsLabel:         document.getElementById('ws-label'),
  wsDot:           null,  // set after DOMContentLoaded
  bottomPanel:     document.getElementById('bottom-panel'),
  bottomHeader:    document.getElementById('bottom-panel-header'),
  xtermContainer:  document.getElementById('xterm-container'),
  debugLog:        document.getElementById('debug-log'),
  aiChat:          document.getElementById('ai-chat'),
  aiChatInput:     document.getElementById('ai-chat-input'),
  btnSendAi:       document.getElementById('btn-send-ai'),
  currentModel:    document.getElementById('current-model-label'),
  suggestionBar:   document.getElementById('suggestion-bar'),
  suggestionText:  document.getElementById('suggestion-text'),
  btnApplySugg:    document.getElementById('btn-apply-sugg'),
  btnDismissSugg:  document.getElementById('btn-dismiss-sugg'),
  sidebar:         document.getElementById('sidebar'),
  sidebarResizer:  document.getElementById('sidebar-resizer'),
  cmdOverlay:      document.getElementById('cmd-palette-overlay'),
  cpInput:         document.getElementById('cp-input'),
  cpResults:       document.getElementById('cp-results'),
  contextMenu:     document.getElementById('context-menu'),
  statusBrianState: document.getElementById('sb-brian-state'),
  sbCursor:        document.getElementById('sb-cursor'),
  sbLang:          document.getElementById('sb-lang-mode'),
  pillFile:        document.getElementById('pill-file'),
  pillSelection:   document.getElementById('pill-selection'),
  aiStatusDot:     document.getElementById('ai-status-dot'),
  aiStatusLabel:   document.getElementById('ai-status-label'),
  gitStatusArea:   document.getElementById('git-status-area'),
};

// ═══════════════════════════════════════════════════════
// WEBSOCKET
// ═══════════════════════════════════════════════════════
function connectBackend() {
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    wsReady = true;
    setWsStatus(true);
    sendMsg({ type: 'scan_workspace' });
    sendMsg({ type: 'git_status' });
    sendMsg({ type: 'get_sessions' });
    appendDebugLog('[WS] Connected to Brian backend.');
  };

  ws.onmessage = ({ data }) => {
    try { handleMsg(JSON.parse(data)); }
    catch (e) { appendDebugLog('[WS] Bad message: ' + data.slice(0, 80)); }
  };

  ws.onclose = () => {
    wsReady = false;
    setWsStatus(false);
    appendDebugLog('[WS] Disconnected. Retrying in 3s…');
    reconnectTimer = setTimeout(connectBackend, 3000);
  };

  ws.onerror = () => ws.close();
}

function sendMsg(obj) {
  if (ws && ws.readyState === WebSocket.OPEN)
    ws.send(JSON.stringify(obj));
}

function setWsStatus(online) {
  dom.wsBadge.classList.toggle('offline', !online);
  dom.wsLabel.textContent = online ? 'SYNCED' : 'OFFLINE';
  dom.aiStatusDot.classList.toggle('offline', !online);
  dom.aiStatusLabel.textContent = online ? 'SYNCED' : 'OFFLINE';
}

// ═══════════════════════════════════════════════════════
// MESSAGE ROUTER
// ═══════════════════════════════════════════════════════
function handleMsg(msg) {
  switch (msg.type) {

    case 'workspace_structure':
      workspaceFiles = msg.files || [];
      if (msg.workspace_name) dom.workspaceName.textContent = msg.workspace_name;
      renderTree();
      break;

    case 'file_content':
      openFile(msg.path, msg.content);
      break;

    case 'save_success':
      tabDirty[msg.path] = false;
      renderTabs();
      appendDebugLog(`[SAVE] ${msg.path}`);
      break;

    case 'chat_response':
      appendChatMsg(msg.text, 'brian');
      setModelBadge(msg.model);
      break;

    case 'ai_edit':
      applyAiEdit(msg.path, msg.content, msg.explanation);
      setModelBadge(msg.model);
      break;

    case 'suggestion':
      showSuggestion(msg.text, msg.edit);
      break;

    case 'run_output':
      logToTerminal(msg.output);
      break;

    case 'git_status_result':
      renderGitStatus(msg.status || '');
      break;

    case 'search_results':
      renderSearchResults(msg.results || []);
      break;

    case 'sessions_list':
      renderSessionsDropdown(msg.sessions);
      break;

    case 'session_loaded':
      loadChatMessages(msg.messages);
      break;

    case 'brian_state':
      setBrianState(msg.state);
      break;

    default:
      appendDebugLog('[MSG] ' + JSON.stringify(msg).slice(0, 120));
  }
}

function renderSessionsDropdown(sessions) {
  const select = document.getElementById('select-session');
  if (!select) return;
  select.innerHTML = '<option value="">-- Load Past Session --</option>';
  sessions.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s.id;
    opt.textContent = s.title;
    if (s.id === activeSessionId) {
      opt.selected = true;
    }
    select.appendChild(opt);
  });
}

function loadChatMessages(messages) {
  dom.aiChat.innerHTML = '';
  if (!messages || !messages.length) {
    appendChatMsg("Sir, this is a fresh conversation session. How can I serve you?", "brian");
    return;
  }
  messages.forEach(m => {
    appendChatMsg(m.text, m.role);
    if (m.model) {
      setModelBadge(m.model);
    }
  });
}

// ═══════════════════════════════════════════════════════
// FILE TREE
// ═══════════════════════════════════════════════════════
const FILE_ICONS = {
  py:   ['fa-brands fa-python', 'py'],
  js:   ['fa-brands fa-js',     'js'],
  jsx:  ['fa-brands fa-react',  'js'],
  ts:   ['fa-solid fa-t',       'js'],
  tsx:  ['fa-brands fa-react',  'js'],
  html: ['fa-brands fa-html5',  'html'],
  css:  ['fa-brands fa-css3-alt','css'],
  json: ['fa-solid fa-braces',  'json'],
  md:   ['fa-solid fa-markdown','md'],
  txt:  ['fa-solid fa-file-lines',''],
  sh:   ['fa-solid fa-terminal',''],
  bat:  ['fa-solid fa-terminal',''],
  env:  ['fa-solid fa-key',     ''],
  gitignore: ['fa-brands fa-git-alt',''],
};

function getFileIcon(name) {
  const ext = name.split('.').pop().toLowerCase();
  const entry = FILE_ICONS[ext] || FILE_ICONS[name.toLowerCase()];
  if (entry) return { cls: entry[0], typeClass: entry[1] };
  return { cls: 'fa-solid fa-file-code', typeClass: '' };
}

function renderTree() {
  const tree = dom.fileTree;
  tree.innerHTML = '';
  if (!workspaceFiles.length) {
    tree.innerHTML = '<div class="tree-loading"><i class="fa-solid fa-folder-open"></i> Empty workspace</div>';
    return;
  }
  workspaceFiles.forEach(item => {
    const el = document.createElement('div');
    el.dataset.path  = item.path;
    el.dataset.type  = item.type;
    el.dataset.depth = item.depth || 1;

    if (item.type === 'folder') {
      const isOpen = treeState[item.path] ?? false;
      el.className = `tree-item folder${isOpen ? ' open' : ''}`;
      el.innerHTML = `
        <i class="fa-solid fa-chevron-right ti-chevron"></i>
        <i class="fa-solid fa-folder ti-icon"></i>
        <span class="ti-name">${escHtml(item.name)}</span>`;
      el.onclick = (e) => { e.stopPropagation(); toggleFolder(item, el); };
    } else {
      const icon = getFileIcon(item.name);
      el.className = `tree-item file ${icon.typeClass}`;
      el.innerHTML = `
        <i class="${icon.cls} ti-icon"></i>
        <span class="ti-name">${escHtml(item.name)}</span>`;
      el.onclick = (e) => { e.stopPropagation(); sendMsg({ type: 'read_file', path: item.path }); };
    }

    // Context menu
    el.oncontextmenu = (e) => { e.preventDefault(); showContextMenu(e, item); };

    tree.appendChild(el);
  });

  // Refresh active tab highlight
  highlightTreeItem(activeTab);
}

function toggleFolder(item, el) {
  const isOpen = treeState[item.path] ?? false;
  treeState[item.path] = !isOpen;
  el.classList.toggle('open', !isOpen);

  // Show/hide children
  let sib = el.nextElementSibling;
  while (sib && parseInt(sib.dataset.depth) > parseInt(el.dataset.depth)) {
    sib.style.display = isOpen ? 'none' : '';
    sib = sib.nextElementSibling;
  }
}

function highlightTreeItem(path) {
  document.querySelectorAll('.tree-item').forEach(el => el.classList.remove('active'));
  if (!path) return;
  const el = document.querySelector(`.tree-item[data-path="${CSS.escape(path)}"]`);
  if (el) el.classList.add('active');
}

// ═══════════════════════════════════════════════════════
// MONACO EDITOR INIT
// ═══════════════════════════════════════════════════════
require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs' } });

require(['vs/editor/editor.main'], function () {
  monacoLoaded = true;

  monaco.editor.defineTheme('brianTheme', {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'comment',   foreground: '4A6A80', fontStyle: 'italic' },
      { token: 'keyword',   foreground: '4FC3F7', fontStyle: 'bold' },
      { token: 'string',    foreground: 'A5D6A7' },
      { token: 'number',    foreground: 'FFCC80' },
      { token: 'regexp',    foreground: 'FFAB91' },
      { token: 'type',      foreground: '80CBC4' },
      { token: 'class',     foreground: 'FFE082' },
      { token: 'function',  foreground: '81D4FA' },
      { token: 'variable',  foreground: 'E2F1FC' },
      { token: 'delimiter', foreground: '5C7A96' },
    ],
    colors: {
      'editor.background':                '#040f20',
      'editor.foreground':                '#C8DFF2',
      'editorCursor.foreground':          '#4FC3F7',
      'editor.lineHighlightBackground':   '#061428',
      'editorLineNumber.foreground':      '#2E4A63',
      'editorLineNumber.activeForeground':'#4FC3F7',
      'editor.selectionBackground':       '#0d2a56',
      'editor.inactiveSelectionBackground':'#091e3d',
      'editorWidget.background':          '#020c1a',
      'editorSuggestWidget.background':   '#020c1a',
      'editorSuggestWidget.border':       '#0d2a56',
      'editorSuggestWidget.selectedBackground': '#061428',
      'list.hoverBackground':             '#061428',
      'scrollbarSlider.background':       '#0d2a5640',
      'scrollbarSlider.hoverBackground':  '#0d2a5680',
      'minimap.background':               '#020c1a',
    }
  });

  editor = monaco.editor.create(dom.monacoContainer, {
    theme:              'brianTheme',
    automaticLayout:    true,
    fontSize:           14,
    fontFamily:         "'Fira Code', 'Cascadia Code', Consolas, monospace",
    fontLigatures:      true,
    lineHeight:         22,
    minimap:            { enabled: true, maxColumn: 80 },
    smoothScrolling:    true,
    cursorSmoothCaretAnimation: 'on',
    renderWhitespace:   'selection',
    bracketPairColorization: { enabled: true },
    guides:             { bracketPairs: true, indentation: true },
    padding:            { top: 12, bottom: 12 },
    suggest:            { preview: true },
    quickSuggestions:   { other: true, comments: false, strings: false },
    wordWrap:           'off',
    scrollBeyondLastLine: false,
  });

  // Ctrl+S → save
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, saveActive);

  // Track cursor position → status bar
  editor.onDidChangeCursorPosition(({ position }) => {
    dom.sbCursor.textContent = `Ln ${position.lineNumber}, Col ${position.column}`;
  });

  // Track content changes → mark dirty
  editor.onDidChangeModelContent(() => {
    if (activeTab) {
      tabDirty[activeTab] = true;
      renderTabs();
    }
    updateContextPills();
  });

  // Selection change → context pills
  editor.onDidChangeCursorSelection(updateContextPills);

  connectBackend();
});

// ═══════════════════════════════════════════════════════
// FILE OPEN / TABS
// ═══════════════════════════════════════════════════════
function langFromPath(path) {
  const ext = path.split('.').pop().toLowerCase();
  const map = {
    py: 'python', js: 'javascript', jsx: 'javascript', ts: 'typescript',
    tsx: 'typescript', html: 'html', css: 'css', json: 'json',
    md: 'markdown', sh: 'shell', bat: 'bat', yaml: 'yaml', yml: 'yaml',
    toml: 'ini', env: 'ini', txt: 'plaintext',
  };
  return map[ext] || 'plaintext';
}

function openFile(path, content) {
  if (!monacoLoaded) return;

  // Create or reuse Monaco model
  if (!tabModels[path]) {
    tabModels[path] = monaco.editor.createModel(content, langFromPath(path));
  } else {
    // Refresh content if it changed on disk
    if (tabModels[path].getValue() !== content) {
      tabModels[path].setValue(content);
    }
  }

  if (!openTabs.includes(path)) {
    openTabs.push(path);
    tabDirty[path] = false;
  }

  switchToTab(path);
}

function switchToTab(path) {
  if (!tabModels[path]) { sendMsg({ type: 'read_file', path }); return; }
  activeTab = path;
  editor.setModel(tabModels[path]);

  dom.splash.classList.add('hidden');
  dom.monacoContainer.classList.add('visible');

  updateBreadcrumb(path);
  dom.activeFileLabel.textContent = path.split(/[\\/]/).pop();
  dom.sbLang.textContent = langFromPath(path).charAt(0).toUpperCase() + langFromPath(path).slice(1);
  dom.pillFile.querySelector('span') && (dom.pillFile.textContent = '');
  dom.pillFile.innerHTML = `<i class="fa-solid fa-file-code"></i> ${path.split(/[\\/]/).pop()}`;

  renderTabs();
  highlightTreeItem(path);
  editor.focus();
}

function renderTabs() {
  dom.tabsBar.innerHTML = '';
  if (!openTabs.length) {
    dom.tabsBar.appendChild(dom.noTabsHint);
    return;
  }

  openTabs.forEach(path => {
    const filename = path.split(/[\\/]/).pop();
    const icon     = getFileIcon(filename);
    const isActive = path === activeTab;
    const isDirty  = tabDirty[path];

    const tab = document.createElement('div');
    tab.className = `editor-tab${isActive ? ' active' : ''}${isDirty ? ' modified' : ''}`;
    tab.title     = path;
    tab.innerHTML = `
      <i class="${icon.cls} tab-icon"></i>
      <span class="tab-name">${escHtml(filename)}</span>
      <button class="tab-close" title="Close"><i class="fa-solid fa-xmark"></i></button>`;

    tab.onclick = (e) => {
      if (e.target.closest('.tab-close')) { e.stopPropagation(); closeTab(path); }
      else switchToTab(path);
    };
    dom.tabsBar.appendChild(tab);
  });
}

function closeTab(path) {
  // Warn if dirty
  if (tabDirty[path]) {
    if (!confirm(`${path.split(/[\\/]/).pop()} has unsaved changes. Close anyway?`)) return;
  }
  openTabs = openTabs.filter(t => t !== path);
  if (tabModels[path]) { tabModels[path].dispose(); delete tabModels[path]; }
  delete tabDirty[path];

  if (activeTab === path) {
    activeTab = openTabs[openTabs.length - 1] || null;
    if (activeTab) switchToTab(activeTab);
    else {
      editor.setModel(null);
      dom.splash.classList.remove('hidden');
      dom.monacoContainer.classList.remove('visible');
      dom.activeFileLabel.textContent = 'No file open';
      updateBreadcrumb(null);
    }
  }
  renderTabs();
}

function saveActive() {
  if (!activeTab || !editor) return;
  const content = editor.getValue();
  sendMsg({ type: 'save_file', path: activeTab, content });
}

// ═══════════════════════════════════════════════════════
// BREADCRUMB
// ═══════════════════════════════════════════════════════
function updateBreadcrumb(path) {
  dom.breadcrumb.innerHTML = '';
  if (!path) return;
  const parts = path.replace(/\\/g, '/').split('/');
  parts.forEach((part, i) => {
    if (i > 0) {
      const sep = document.createElement('span');
      sep.className = 'bc-sep';
      sep.textContent = ' › ';
      dom.breadcrumb.appendChild(sep);
    }
    const span = document.createElement('span');
    span.className = 'bc-item';
    span.textContent = part;
    const subPath = parts.slice(0, i + 1).join('/');
    span.onclick = () => {
      const item = workspaceFiles.find(f => f.path === subPath && f.type === 'file');
      if (item) sendMsg({ type: 'read_file', path: subPath });
    };
    dom.breadcrumb.appendChild(span);
  });
}

// ═══════════════════════════════════════════════════════
// AI CHAT
// ═══════════════════════════════════════════════════════
let thinkingBubble = null;

function appendChatMsg(text, sender, isThinking = false) {
  // Remove previous thinking bubble
  if (sender === 'brian' && thinkingBubble) {
    thinkingBubble.remove();
    thinkingBubble = null;
  }

  const msg = document.createElement('div');
  msg.className = `chat-msg ${sender}${isThinking ? ' thinking' : ''}`;

  const avatar = sender === 'brian'
    ? '<i class="fa-solid fa-brain"></i>'
    : '<i class="fa-solid fa-user"></i>';

  const displayText = sender === 'brian'
    ? (typeof marked !== 'undefined' ? marked.parse(text) : escHtml(text).replace(/\n/g, '<br>'))
    : escHtml(text).replace(/\n/g, '<br>');

  const meta = sender === 'brian' ? 'BRIAN · Coding Agent' : 'You';

  msg.innerHTML = `
    <div class="msg-avatar">${avatar}</div>
    <div class="msg-body">
      <p>${displayText}</p>
      <div class="msg-meta">${meta}</div>
    </div>`;

  dom.aiChat.appendChild(msg);
  dom.aiChat.scrollTop = dom.aiChat.scrollHeight;

  if (isThinking) thinkingBubble = msg;
  return msg;
}

function submitInstruction() {
  const text = dom.aiChatInput.value.trim();
  if (!text) return;

  appendChatMsg(text, 'user');
  dom.aiChatInput.value = '';

  // Typing indicator
  appendChatMsg('Thinking…', 'brian', true);
  dom.btnSendAi.classList.add('loading');

  const selection = (editor && !editor.getSelection().isEmpty())
    ? editor.getModel()?.getValueInRange(editor.getSelection()) || ''
    : '';

  sendMsg({
    type:          'chat_instruction',
    text,
    active_file:   activeTab,
    selected_code: selection,
    session_id:    activeSessionId,
  });
}

dom.btnSendAi.onclick = submitInstruction;
dom.aiChatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    submitInstruction();
  }
});

// Session Event Listeners
const btnNewSession = document.getElementById('btn-new-session');
const selectSession = document.getElementById('select-session');

if (btnNewSession) {
  btnNewSession.onclick = () => {
    activeSessionId = generateSessionId();
    loadChatMessages([]);
    if (selectSession) selectSession.value = "";
    sendMsg({ type: 'get_sessions' });
  };
}

if (selectSession) {
  selectSession.onchange = () => {
    const val = selectSession.value;
    if (val) {
      activeSessionId = val;
      sendMsg({ type: 'load_session', session_id: val });
    }
  };
}

// When backend responds, the loading state is cleared by appendChatMsg
const originalAppendChatMsg = appendChatMsg;

// ═══════════════════════════════════════════════════════
// AI EDITS
// ═══════════════════════════════════════════════════════
function applyAiEdit(path, content, explanation) {
  dom.btnSendAi.classList.remove('loading');

  if (path === activeTab && editor) {
    const model = editor.getModel();
    editor.executeEdits('brian-ai', [{
      range: model.getFullModelRange(),
      text: content,
      forceMoveMarkers: true,
    }]);
    tabDirty[path] = true;
    renderTabs();
  } else {
    // Open the file with the edited content
    if (tabModels[path]) {
      tabModels[path].setValue(content);
    } else {
      tabModels[path] = monaco.editor.createModel(content, langFromPath(path));
      if (!openTabs.includes(path)) openTabs.push(path);
    }
    tabDirty[path] = true;
    renderTabs();
  }

  if (explanation) appendChatMsg(explanation, 'brian');
}

function setModelBadge(model) {
  if (!model) return;
  const short = model.split('/').pop().replace(':free', '');
  dom.currentModel.textContent = model.includes('cohere') ? model.split('/').pop() : model;
}

function showSuggestion(text, edit) {
  currentSuggestion = edit;
  dom.suggestionText.textContent = text;
  dom.suggestionBar.classList.remove('hidden');
}

dom.btnApplySugg.onclick = () => {
  if (editor && currentSuggestion) {
    const range = new monaco.Range(
      currentSuggestion.startLine, 1,
      currentSuggestion.endLine,
      editor.getModel().getLineMaxColumn(currentSuggestion.endLine)
    );
    editor.executeEdits('brian-sugg', [{ range, text: currentSuggestion.text, forceMoveMarkers: true }]);
  }
  dom.suggestionBar.classList.add('hidden');
  currentSuggestion = null;
};

dom.btnDismissSugg.onclick = () => {
  dom.suggestionBar.classList.add('hidden');
  currentSuggestion = null;
};

// ═══════════════════════════════════════════════════════
// CONTEXT PILLS (AI input area)
// ═══════════════════════════════════════════════════════
function updateContextPills() {
  if (!editor) return;
  const sel = editor.getSelection();
  const hasSelection = sel && !sel.isEmpty();
  dom.pillSelection.style.display = hasSelection ? '' : 'none';
}

// ═══════════════════════════════════════════════════════
// TERMINAL (xterm.js)
// ═══════════════════════════════════════════════════════
let term    = null;
let fitAddon = null;

function initTerminal() {
  if (term) return;
  term = new Terminal({
    theme: {
      background:        '#010810',
      foreground:        '#C8DFF2',
      cursor:            '#4FC3F7',
      cursorAccent:      '#020c1a',
      selectionBackground: '#0d2a56',
      black:             '#020c1a',
      brightBlack:       '#2E4A63',
      blue:              '#4FC3F7',
      brightBlue:        '#81D4FA',
      green:             '#69F0AE',
      brightGreen:       '#B9F6CA',
      red:               '#EF9A9A',
      yellow:            '#FFD54F',
    },
    fontFamily:  "'Fira Code', 'Cascadia Code', Consolas, monospace",
    fontSize:    12.5,
    lineHeight:  1.4,
    cursorBlink: true,
    cursorStyle: 'block',
    scrollback:  5000,
  });

  fitAddon = new FitAddon.FitAddon();
  term.loadAddon(fitAddon);
  term.open(dom.xtermContainer);
  fitAddon.fit();

  term.writeln('\x1b[1;36mBRIAN Integrated Console\x1b[0m  — Type Ctrl+\` to toggle');
  term.writeln('\x1b[2m─────────────────────────────────────────────\x1b[0m');
  term.write('\r\n$ ');

  term.onData(data => sendMsg({ type: 'terminal_input', data }));

  // Keep terminal fitted when panel resizes
  new ResizeObserver(() => { if (fitAddon) fitAddon.fit(); })
    .observe(dom.xtermContainer);
}

function logToTerminal(data) {
  if (term) term.write(data);
  else appendDebugLog(data);
}

function appendDebugLog(text) {
  dom.debugLog.textContent += text + '\n';
  dom.debugLog.scrollTop = dom.debugLog.scrollHeight;
}

// ═══════════════════════════════════════════════════════
// BOTTOM PANEL
// ═══════════════════════════════════════════════════════
function openBottomPanel(tab) {
  dom.bottomPanel.classList.remove('collapsed');
  if (tab) switchBottomTab(tab);
  if (fitAddon) setTimeout(() => fitAddon.fit(), 100);
}

function switchBottomTab(tab) {
  document.querySelectorAll('.bp-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.btab-content').forEach(c => c.classList.remove('active'));
  const btn = document.querySelector(`.bp-tab[data-btab="${tab}"]`);
  const content = document.getElementById(`btab-${tab}`);
  if (btn) btn.classList.add('active');
  if (content) content.classList.add('active');
  if (tab === 'terminal' && fitAddon) setTimeout(() => fitAddon.fit(), 60);
}

document.querySelectorAll('.bp-tab').forEach(btn => {
  btn.onclick = () => {
    if (dom.bottomPanel.classList.contains('collapsed')) openBottomPanel(btn.dataset.btab);
    else switchBottomTab(btn.dataset.btab);
  };
});

document.getElementById('btn-close-panel').onclick  = () => dom.bottomPanel.classList.add('collapsed');
document.getElementById('btn-maximize-panel').onclick = () => dom.bottomPanel.classList.toggle('maximized');
document.getElementById('btn-new-terminal').onclick   = () => openBottomPanel('terminal');

// Panel resize (drag header)
dom.bottomHeader.addEventListener('mousedown', (e) => {
  if (e.target.closest('button') || e.target.closest('.bp-tab')) return;
  panelResizing = true;
  panelStartY   = e.clientY;
  panelStartH   = dom.bottomPanel.offsetHeight;
  dom.bottomPanel.classList.remove('collapsed', 'maximized');
});

document.addEventListener('mousemove', (e) => {
  if (!panelResizing) return;
  const delta = panelStartY - e.clientY;
  const newH  = Math.max(60, Math.min(window.innerHeight * 0.8, panelStartH + delta));
  dom.bottomPanel.style.height = newH + 'px';
});

document.addEventListener('mouseup', () => {
  if (panelResizing && fitAddon) fitAddon.fit();
  panelResizing = false;
});

// ═══════════════════════════════════════════════════════
// SIDEBAR RESIZER
// ═══════════════════════════════════════════════════════
dom.sidebarResizer.addEventListener('mousedown', (e) => {
  sidebarResizing = true;
  dom.sidebarResizer.classList.add('dragging');
  e.preventDefault();
});

document.addEventListener('mousemove', (e) => {
  if (!sidebarResizing) return;
  const abRect = document.getElementById('activity-bar').getBoundingClientRect();
  const w = Math.max(160, Math.min(500, e.clientX - abRect.right));
  dom.sidebar.style.width = w + 'px';
  document.documentElement.style.setProperty('--sidebar-w', w + 'px');
});

document.addEventListener('mouseup', () => {
  sidebarResizing = false;
  dom.sidebarResizer.classList.remove('dragging');
});

// ═══════════════════════════════════════════════════════
// ACTIVITY BAR — panel switching
// ═══════════════════════════════════════════════════════
const PANELS = { explorer: 'panel-explorer', search: 'panel-search', git: 'panel-git', extensions: 'panel-extensions' };

document.querySelectorAll('.ab-btn[data-panel]').forEach(btn => {
  btn.onclick = () => {
    const panelId = btn.dataset.panel;
    const isActive = btn.classList.contains('active');

    document.querySelectorAll('.ab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel-view').forEach(p => p.classList.remove('active'));

    if (isActive) {
      dom.sidebar.classList.add('collapsed');
    } else {
      dom.sidebar.classList.remove('collapsed');
      btn.classList.add('active');
      const panel = document.getElementById(PANELS[panelId]);
      if (panel) panel.classList.add('active');
    }
  };
});

document.getElementById('ab-hud').onclick  = () => window.open('http://localhost:9001', '_blank');
document.getElementById('ab-settings').onclick = () => appendChatMsg("Settings panel coming soon, sir.", 'brian');

// ═══════════════════════════════════════════════════════
// COMMAND PALETTE
// ═══════════════════════════════════════════════════════
function openCommandPalette() {
  dom.cmdOverlay.classList.remove('hidden');
  dom.cpInput.value = '';
  dom.cpInput.focus();
  renderCpResults('');
}

function closeCommandPalette() {
  dom.cmdOverlay.classList.add('hidden');
}

dom.cmdOverlay.addEventListener('click', (e) => {
  if (e.target === dom.cmdOverlay) closeCommandPalette();
});

document.getElementById('cp-close').onclick = closeCommandPalette;
document.getElementById('cmd-palette-trigger').onclick = openCommandPalette;

dom.cpInput.addEventListener('input', () => renderCpResults(dom.cpInput.value.trim()));

dom.cpInput.addEventListener('keydown', (e) => {
  const items = dom.cpResults.querySelectorAll('.cp-item');
  if (e.key === 'ArrowDown') {
    cpIndex = Math.min(cpIndex + 1, items.length - 1);
    updateCpSelection(items);
  } else if (e.key === 'ArrowUp') {
    cpIndex = Math.max(cpIndex - 1, 0);
    updateCpSelection(items);
  } else if (e.key === 'Enter') {
    const selected = items[cpIndex] || items[0];
    if (selected) selected.click();
  } else if (e.key === 'Escape') {
    closeCommandPalette();
  }
});

function updateCpSelection(items) {
  items.forEach((el, i) => el.classList.toggle('selected', i === cpIndex));
  if (items[cpIndex]) items[cpIndex].scrollIntoView({ block: 'nearest' });
}

const BUILTIN_COMMANDS = [
  { label: 'Save File',              icon: 'fa-solid fa-floppy-disk', action: saveActive },
  { label: 'Toggle Sidebar',         icon: 'fa-solid fa-sidebar',     action: () => dom.sidebar.classList.toggle('collapsed') },
  { label: 'Toggle Terminal',        icon: 'fa-solid fa-terminal',     action: () => dom.bottomPanel.classList.toggle('collapsed') },
  { label: 'Refresh File Tree',      icon: 'fa-solid fa-rotate',      action: () => sendMsg({ type: 'scan_workspace' }) },
  { label: 'Open Brian HUD',         icon: 'fa-solid fa-circle-nodes', action: () => window.open('http://localhost:9001', '_blank') },
  { label: 'Run Active File',        icon: 'fa-solid fa-play',        action: runActiveFile },
  { label: 'Commit & Push (Git)',    icon: 'fa-solid fa-cloud-arrow-up', action: () => openBottomPanel('git') },
];

function renderCpResults(query) {
  cpIndex = -1;
  dom.cpResults.innerHTML = '';
  const q = query.toLowerCase();

  // Files
  const matchedFiles = workspaceFiles
    .filter(f => f.type === 'file' && f.path.toLowerCase().includes(q))
    .slice(0, 8);

  if (matchedFiles.length) {
    const sec = document.createElement('div');
    sec.className = 'cp-section-header';
    sec.textContent = 'FILES';
    dom.cpResults.appendChild(sec);

    matchedFiles.forEach(f => {
      const item = document.createElement('div');
      const icon = getFileIcon(f.name);
      item.className = 'cp-item file';
      item.innerHTML = `<i class="${icon.cls}"></i><span class="cp-item-name">${escHtml(f.name)}</span><span class="cp-item-path">${escHtml(f.path)}</span>`;
      item.onclick = () => { closeCommandPalette(); sendMsg({ type: 'read_file', path: f.path }); };
      dom.cpResults.appendChild(item);
    });
  }

  // Commands
  const matchedCmds = BUILTIN_COMMANDS.filter(c => c.label.toLowerCase().includes(q));
  if (matchedCmds.length) {
    const sec = document.createElement('div');
    sec.className = 'cp-section-header';
    sec.textContent = 'COMMANDS';
    dom.cpResults.appendChild(sec);

    matchedCmds.forEach(c => {
      const item = document.createElement('div');
      item.className = 'cp-item';
      item.innerHTML = `<i class="${c.icon}"></i><span class="cp-item-name">${escHtml(c.label)}</span>`;
      item.onclick = () => { closeCommandPalette(); c.action(); };
      dom.cpResults.appendChild(item);
    });
  }
}

// ═══════════════════════════════════════════════════════
// CONTEXT MENU (right-click on file tree)
// ═══════════════════════════════════════════════════════
function showContextMenu(e, item) {
  contextMenuTarget = item;
  const menu = dom.contextMenu;
  menu.classList.remove('hidden');
  menu.style.left = e.pageX + 'px';
  menu.style.top  = e.pageY + 'px';
  document.getElementById('cm-open').style.display = item.type === 'file' ? '' : 'none';
}

document.addEventListener('click', () => dom.contextMenu.classList.add('hidden'));

document.getElementById('cm-open').onclick = () => {
  if (contextMenuTarget) sendMsg({ type: 'read_file', path: contextMenuTarget.path });
};

document.getElementById('cm-rename').onclick = () => {
  if (!contextMenuTarget) return;
  const newName = prompt('Rename to:', contextMenuTarget.name);
  if (newName && newName !== contextMenuTarget.name) {
    sendMsg({ type: 'rename_file', old_path: contextMenuTarget.path, new_name: newName });
  }
};

document.getElementById('cm-delete').onclick = () => {
  if (!contextMenuTarget) return;
  if (confirm(`Delete ${contextMenuTarget.name}?`)) {
    sendMsg({ type: 'delete_file', path: contextMenuTarget.path });
    if (openTabs.includes(contextMenuTarget.path)) closeTab(contextMenuTarget.path);
  }
};

document.getElementById('cm-new-file').onclick = () => {
  const name = prompt('New file name:');
  if (name) {
    const dir = contextMenuTarget?.type === 'folder' ? contextMenuTarget.path : (contextMenuTarget?.path?.split('/').slice(0, -1).join('/') || '');
    sendMsg({ type: 'new_file', dir, name });
  }
};

// ═══════════════════════════════════════════════════════
// GIT PANEL
// ═══════════════════════════════════════════════════════
function renderGitStatus(status) {
  const area = dom.gitStatusArea;
  if (!status.trim()) {
    area.innerHTML = '<div class="git-placeholder"><i class="fa-solid fa-circle-check"></i> Working tree clean</div>';
    return;
  }
  area.innerHTML = '';
  status.split('\n').filter(Boolean).forEach(line => {
    const el = document.createElement('div');
    el.className = 'tree-item';
    el.innerHTML = `<i class="fa-solid fa-file-circle-exclamation ti-icon"></i><span class="ti-name">${escHtml(line)}</span>`;
    area.appendChild(el);
  });
}

document.getElementById('btn-git-refresh').onclick = () => sendMsg({ type: 'git_status' });
document.getElementById('btn-git-commit-push').onclick = () => {
  const msg = document.getElementById('git-commit-msg').value.trim();
  if (!msg) { alert('Please enter a commit message.'); return; }
  sendMsg({ type: 'git_commit_push', message: msg });
  document.getElementById('git-commit-msg').value = '';
};

// ═══════════════════════════════════════════════════════
// SEARCH
// ═══════════════════════════════════════════════════════
document.getElementById('btn-run-search').onclick = runSearch;
document.getElementById('search-query').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') runSearch();
});

function runSearch() {
  const q = document.getElementById('search-query').value.trim();
  if (!q) return;
  sendMsg({
    type:       'search',
    query:      q,
    case_sensitive: document.getElementById('search-case').checked,
    regex:      document.getElementById('search-regex').checked,
    whole_word: document.getElementById('search-word').checked,
  });
}

function renderSearchResults(results) {
  const area = document.getElementById('search-results');
  area.innerHTML = '';
  if (!results.length) {
    area.innerHTML = '<div style="color:var(--text-muted);font-size:12px;padding:8px">No results found.</div>';
    return;
  }
  results.forEach(r => {
    const el = document.createElement('div');
    el.className = 'search-result-item';
    el.innerHTML = `
      <div class="sr-file">${escHtml(r.file)}</div>
      <div class="sr-line">Line ${r.line}: <span class="sr-match">${escHtml(r.context || '')}</span></div>`;
    el.onclick = () => {
      sendMsg({ type: 'read_file', path: r.file });
      setTimeout(() => {
        if (editor) editor.setPosition({ lineNumber: r.line, column: 1 });
      }, 600);
    };
    area.appendChild(el);
  });
}

// ═══════════════════════════════════════════════════════
// TOOLBAR ACTIONS
// ═══════════════════════════════════════════════════════
document.getElementById('btn-run-active').onclick = runActiveFile;
document.getElementById('btn-save-active').onclick = saveActive;
document.getElementById('btn-run-file-ai').onclick = runActiveFile;
document.getElementById('btn-change-folder').onclick = () => {
  const newPath = prompt('Enter absolute path of workspace directory:', '');
  if (newPath) {
    sendMsg({ type: 'change_workspace', path: newPath });
  }
};
document.getElementById('btn-refresh-tree').onclick = () => sendMsg({ type: 'scan_workspace' });
document.getElementById('btn-collapse-all').onclick = () => {
  treeState = {};
  renderTree();
};
document.getElementById('btn-new-file').onclick = () => {
  const name = prompt('New file name (relative to workspace):');
  if (name) sendMsg({ type: 'new_file', dir: '', name });
};
document.getElementById('btn-new-folder').onclick = () => {
  const name = prompt('New folder name:');
  if (name) sendMsg({ type: 'new_folder', name });
};

document.getElementById('btn-attach-context').onclick = () => {
  if (!activeTab) return;
  const content = editor?.getValue() || '';
  dom.aiChatInput.value += `\n[Full file: ${activeTab}]\n\`\`\`\n${content.slice(0, 2000)}${content.length > 2000 ? '\n…(truncated)' : ''}\n\`\`\`\n`;
  dom.aiChatInput.focus();
};

document.getElementById('btn-voice-input').onclick = () => {
  appendChatMsg('Voice input: say "Hey Brian" to give a coding instruction, sir.', 'brian');
};

function runActiveFile() {
  if (!activeTab) { appendChatMsg('Please open a file first, sir.', 'brian'); return; }
  openBottomPanel('terminal');
  sendMsg({ type: 'run_file', path: activeTab });
}

// ═══════════════════════════════════════════════════════
// BRIAN STATE (from backend)
// ═══════════════════════════════════════════════════════
function setBrianState(state) {
  const label = (state || 'idle').toUpperCase();
  dom.statusBrianState.innerHTML = `<span class="sb-dot"></span> ${label}`;
}

// ═══════════════════════════════════════════════════════
// KEYBOARD SHORTCUTS (global)
// ═══════════════════════════════════════════════════════
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey || e.metaKey) {
    switch (e.key.toLowerCase()) {
      case 'p':
        e.preventDefault();
        if (dom.cmdOverlay.classList.contains('hidden')) openCommandPalette();
        break;
      case 'b':
        e.preventDefault();
        dom.sidebar.classList.toggle('collapsed');
        break;
      case '`':
        e.preventDefault();
        if (dom.bottomPanel.classList.contains('collapsed')) openBottomPanel('terminal');
        else dom.bottomPanel.classList.add('collapsed');
        break;
      case 's':
        // Handled by Monaco command
        break;
    }
  }
  if (e.key === 'Escape' && !dom.cmdOverlay.classList.contains('hidden')) {
    closeCommandPalette();
  }
  if (e.key === 'F5') { e.preventDefault(); runActiveFile(); }
});

// ═══════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ═══════════════════════════════════════════════════════
// BOOTSTRAP
// ═══════════════════════════════════════════════════════
window.addEventListener('load', () => {
  // Monaco is initialized via the require callback above — terminal init here
  setTimeout(initTerminal, 300);

  // Check if Monaco already loaded (race condition guard)
  if (typeof monaco !== 'undefined' && !editor) {
    // Will be handled by the require callback
  }

  // Apply stored sidebar width preference
  const savedW = localStorage.getItem('sidebarWidth');
  if (savedW) {
    dom.sidebar.style.width = savedW + 'px';
    document.documentElement.style.setProperty('--sidebar-w', savedW + 'px');
  }
});

// Save sidebar width preference on close
window.addEventListener('beforeunload', () => {
  localStorage.setItem('sidebarWidth', dom.sidebar.offsetWidth);
});
