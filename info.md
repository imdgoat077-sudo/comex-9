# Architecture Audit & Integration Plan for `browser-use`

Based on a thorough inspection of your existing codebase, here are the answers to your questions and a detailed architecture audit.

### 1. Current Architecture

1. **Framework/Runtime**: The browser is built with **Electron** (as the runtime container) and **React** (via Vite) for the user interface.
2. **Main Window Creation**: `electron/main.js` is responsible for creating the main application window and configuring Electron's webPreferences.
3. **Tab Management**: Browser tabs are managed purely in the React frontend state within `src/App.jsx` (`const [tabs, setTabs] = useState(...)`).
4. **Web Page Rendering**: Web pages are rendered using Electron's **`<webview>`** tag. This is implemented in `src/components/Apps/IframeViewer.jsx` (which conditionally renders a `<webview>` when running in Electron).
5. **Navigation**: 
   * Handled by the React frontend updating the `url` property of a tab object. 
   * `IframeViewer.jsx` listens for URL changes and calls `webview.loadURL()`. 
   * Back/Forward/Reload use custom DOM events (`comex-webview-nav`) which `IframeViewer.jsx` intercepts to call native webview methods like `webview.goBack()` and `webview.reload()`.
6. **Chat/AI Sidebar**: Implemented in React via `src/components/Chat/ChatDrawer.jsx`. Currently, it uses a mock multi-agent system located in `src/agents/OrchestratorAgent.js` that parses hardcoded strings (like "youtube", "google") instead of using a real LLM.
7. **Communication Architecture**: The frontend communicates with the Electron main process minimally via `electron/preload.js` (exposing `nexusNative` context bridge).
8. **Existing Backend**: **No.** There is currently no Python process, HTTP server, or WebSocket server. The AI logic is completely mocked in client-side JavaScript.

---

### 2. Is Integration with `browser-use` Possible?

**Yes, it is technically possible**, but there are some critical caveats specifically due to how Electron handles rendering.

Your goal:
```text
Existing browser (Electron) --> CDP --> Python (browser-use) --> LLM
```

#### How it would work:
1. **Enable CDP in Electron**: You must launch your Electron app with the remote debugging port enabled. This is done by adding `app.commandLine.appendSwitch('remote-debugging-port', '9222')` to your `electron/main.js` before `app.whenReady()`.
2. **Connect Playwright**: Python `browser-use` uses Playwright under the hood. Playwright has a `chromium.connect_over_cdp('http://localhost:9222')` method. This allows `browser-use` to attach to the running Electron Chromium instance instead of launching a new browser.

#### The `<webview>` Limitation (CRITICAL):
Your project currently renders pages using `<webview>`. Playwright (and by extension, `browser-use`) is designed to work with standard browser tabs (Pages). 
When Playwright connects to Electron via CDP, it will see the main React window as a Page, but interacting with the *contents* of the `<webview>` tag is notoriously difficult because `<webview>` runs as a separate guest `WebContents` out-of-process. Playwright often fails to properly inject scripts or locate elements inside `<webview>` tags over a standard CDP connection.

If `browser-use` fails to "see" inside the `<webview>`, you might need to refactor your rendering from `<webview>` to Electron's **`BrowserView`** or **`WebContentsView`**, which behave much more like standard Chromium tabs over CDP and are generally the recommended modern approach in Electron anyway.

---

### 3. Recommended Integration Architecture

To achieve your vision without breaking the existing app:

**What stays unchanged:**
* The React UI (`App.jsx`, `BrowserNavbar`, etc.)
* The Tab state management
* The Vite/Electron build pipeline

**What needs modification:**
1. `electron/main.js`: Needs to enable the `--remote-debugging-port`.
2. `src/components/Chat/ChatDrawer.jsx`: Needs to replace the mock agent logic with actual HTTP/WebSocket calls to your Python backend.
3. *Potentially* `IframeViewer.jsx`: If `browser-use` struggles to see inside the `<webview>`, you may need to refactor this to use `BrowserView` managed from `main.js`.

**What new components are needed:**
1. **Python Agent Server**: A new Python API server (e.g., FastAPI) running locally. This server will run `browser-use` and connect to the 9Router endpoint.
2. **Frontend-to-Python Bridge**: Your React `ChatDrawer` needs to send the user's prompt to the Python API. The Python API then spins up `browser-use`, connects to Electron's CDP port (`9222`), takes control of the tab, and streams progress logs back to the React UI via WebSockets or Server-Sent Events (SSE).

**How tab assignment works:**
When the user clicks "Send" in the chat, the React app sends the `activeTabId` and current URL to the Python server. `browser-use` connects via CDP, enumerates all available `contexts/pages`, and finds the specific page/webview whose URL matches the active tab, then restricts its operations to that specific Page object.

**How the AI releases the tab:**
`browser-use` completes its task loop and disconnects its CDP session. The Python server sends a "Task Complete" message to the React UI, and the user simply continues using the browser normally.

---

### Summary of Next Steps (When you are ready):

1. **Test CDP Visibility**: Before rewriting anything, we will launch Electron with `--remote-debugging-port=9222` and write a tiny standalone Python Playwright script to see if it can successfully find and interact with DOM elements *inside* your existing `<webview>`.
2. If yes -> Proceed with connecting `browser-use`.
3. If no -> Refactor `<webview>` to `BrowserView`/`WebContentsView` first, then connect `browser-use`.
