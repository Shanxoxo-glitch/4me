/**
 * BRIAN VS Code Extension Code
 * Registers commands and the side panel webview provider.
 */

const vscode = require('vscode');

function activate(context) {
  logger("Brian Extension activated.");

  // Register Sidebar Webview
  const provider = new BrianSidebarProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider("brian-sidebar-view", provider)
  );

  // Command: Ask Brian (opens dialog or focuses panel)
  context.subscriptions.push(
    vscode.commands.registerCommand("brian.ask", async () => {
      const input = await vscode.window.showInputBox({
        prompt: "Ask Brian to write or modify code...",
        placeHolder: "e.g., add try/except error handling to this method"
      });
      if (input) {
        provider.postMessageToWebview({
          type: "user_command",
          text: input,
          code: getActiveSelection()
        });
      }
    })
  );

  // Command: Refactor Code
  context.subscriptions.push(
    vscode.commands.registerCommand("brian.refactor", () => {
      const code = getActiveSelection();
      if (!code) {
        vscode.window.showWarningMessage("Please select some code to refactor, sir.");
        return;
      }
      provider.postMessageToWebview({
        type: "user_command",
        text: "Refactor this code to make it cleaner and more optimal.",
        code: code
      });
      vscode.commands.executeCommand("brian-sidebar-view.focus");
    })
  );

  // Command: Explain Code
  context.subscriptions.push(
    vscode.commands.registerCommand("brian.explain", () => {
      const code = getActiveSelection();
      if (!code) {
        vscode.window.showWarningMessage("Please select some code to explain, sir.");
        return;
      }
      provider.postMessageToWebview({
        type: "user_command",
        text: "Explain what this block of code does in detail.",
        code: code
      });
      vscode.commands.executeCommand("brian-sidebar-view.focus");
    })
  );
}

function getActiveSelection() {
  const editor = vscode.window.activeTextEditor;
  if (editor) {
    const selection = editor.selection;
    return editor.document.getText(selection) || editor.document.getText(); // selected or entire file
  }
  return "";
}

class BrianSidebarProvider {
  constructor(extensionUri) {
    this._extensionUri = extensionUri;
    this._view = undefined;
  }

  resolveWebviewView(webviewView, context, _token) {
    this._view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };

    webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

    // Listen to messages from webview (e.g. apply edits back to the active editor)
    webviewView.webview.onDidReceiveMessage(async (data) => {
      if (data.type === "apply_code") {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
          editor.edit((editBuilder) => {
            const selection = editor.selection;
            const range = selection.isEmpty 
              ? new vscode.Range(0, 0, editor.document.lineCount, 0)
              : selection;
            editBuilder.replace(range, data.code);
          });
          vscode.window.showInformationMessage("Edits successfully applied, sir.");
        }
      }
    });
  }

  postMessageToWebview(msg) {
    if (this._view) {
      this._view.webview.postMessage(msg);
    }
  }

  _getHtmlForWebview(webview) {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    body {
      font-family: var(--vscode-font-family, sans-serif);
      color: var(--vscode-editor-foreground, #ccc);
      background-color: var(--vscode-sideBar-background, #111);
      padding: 10px;
      font-size: 13px;
    }
    .chat-container {
      display: flex;
      flex-direction: column;
      height: 95vh;
    }
    .messages {
      flex: 1;
      overflow-y: auto;
      margin-bottom: 10px;
      padding-right: 5px;
    }
    .bubble {
      padding: 8px 12px;
      border-radius: 8px;
      margin-bottom: 8px;
      max-width: 90%;
      line-height: 1.4;
    }
    .bubble.user {
      background-color: var(--vscode-button-background, #0288D1);
      color: var(--vscode-button-foreground, #fff);
      align-self: flex-end;
      margin-left: auto;
    }
    .bubble.brian {
      background-color: rgba(79, 195, 247, 0.08);
      border-left: 3px solid #4FC3F7;
      align-self: flex-start;
    }
    .input-box {
      width: 100%;
      background-color: var(--vscode-input-background, #222);
      border: 1px solid var(--vscode-input-border, #444);
      color: var(--vscode-input-foreground, #eee);
      padding: 8px;
      border-radius: 4px;
      resize: none;
      outline: none;
      box-sizing: border-box;
    }
    .btn-row {
      display: flex;
      justify-content: flex-end;
      margin-top: 6px;
    }
    button {
      background-color: var(--vscode-button-background, #0066cc);
      color: var(--vscode-button-foreground, #fff);
      border: none;
      padding: 6px 12px;
      cursor: pointer;
      border-radius: 4px;
    }
    button:hover {
      background-color: var(--vscode-button-hoverBackground, #0055aa);
    }
    .code-action {
      margin-top: 6px;
      display: flex;
      justify-content: space-between;
    }
  </style>
</head>
<body>
  <div class="chat-container">
    <div class="messages" id="msg-list">
      <div class="bubble brian">
        Welcome, sir. I am synced with your active editor. Ask me to modify, explain, or refactor code.
      </div>
    </div>
    
    <div id="action-panel" style="display: none; padding: 6px; background: rgba(105,240,174,0.08); border-radius: 4px; margin-bottom: 6px;">
      <span style="color: #69F0AE; font-size: 11px;">Brian has generated edits.</span>
      <div class="code-action">
        <button onclick="applyEdits()" style="background-color: #2e7d32;">Apply to File</button>
        <button onclick="dismissEdits()" style="background-color: #c62828;">Discard</button>
      </div>
    </div>

    <textarea class="input-box" id="user-input" rows="3" placeholder="Ask Brian (Ctrl+Enter)..."></textarea>
    <div class="btn-row">
      <button onclick="sendMsg()">Send</button>
    </div>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    const ws = new WebSocket("ws://localhost:9002");
    let pendingCode = "";

    ws.onopen = () => {
      console.log("Brian VS Code extension connected to local backend.");
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "ai_edit") {
        pendingCode = msg.content;
        addBubble(msg.explanation, "brian");
        document.getElementById("action-panel").style.display = "block";
      } else if (msg.type === "chat_response") {
        addBubble(msg.text, "brian");
      }
    };

    // Receive message from parent extension context
    window.addEventListener("message", event => {
      const message = event.data;
      if (message.type === "user_command") {
        addBubble(message.text, "user");
        ws.send(JSON.stringify({
          type: "chat_instruction",
          text: message.text,
          active_file: "editor.txt", // virtual filename
          selected_code: message.code
        }));
      }
    });

    function addBubble(text, role) {
      const bubble = document.createElement("div");
      bubble.className = "bubble " + role;
      bubble.textContent = text;
      document.getElementById("msg-list").appendChild(bubble);
      document.getElementById("msg-list").scrollTop = document.getElementById("msg-list").scrollHeight;
    }

    function sendMsg() {
      const val = document.getElementById("user-input").value.trim();
      if (!val) return;
      addBubble(val, "user");
      document.getElementById("user-input").value = "";
      
      // Request active context (implied context)
      ws.send(JSON.stringify({
        type: "chat_instruction",
        text: val,
        active_file: "",
        selected_code: ""
      }));
    }

    document.getElementById("user-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        sendMsg();
      }
    });

    function applyEdits() {
      if (pendingCode) {
        vscode.postMessage({ type: "apply_code", code: pendingCode });
      }
      dismissEdits();
    }

    function dismissEdits() {
      document.getElementById("action-panel").style.display = "none";
      pendingCode = "";
    }
  </script>
</body>
</html>`;
  }
}

function deactivate() {}

module.exports = {
  activate,
  deactivate
};

function logger(msg) {
  console.log("[BRIAN EXT] " + msg);
}
