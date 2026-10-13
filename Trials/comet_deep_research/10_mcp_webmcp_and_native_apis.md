# 10 — Model Context Protocol (MCP), WebMCP & Native C++ APIs

## 1. Dual-Tier MCP Architecture

Comet features one of the industry's first native implementations of Anthropic's **Model Context Protocol (MCP)** directly integrated into a Chromium browser fork. MCP is implemented in two distinct tiers:

1. **Native C++ Stdio Daemon (`components/perplexity/mcp/`)**: Spawns local host command-line tools (e.g. SQLite, GitHub CLI, Python scripts) as subprocesses communicating via JSON-RPC 2.0 stdio pipes.
2. **Declarative WebMCP in Blink (`third_party/blink/renderer/core/html/`)**: Extends HTML forms and introduces a dedicated Chrome DevTools Protocol domain (`WebMCP`), enabling web pages to expose tools directly to LLMs without script injection.

```
+-----------------------------------------------------------------------------------------+
|                                    Comet Browser Engine                                 |
|                                                                                         |
|   +------------------------------------+       +------------------------------------+   |
|   |   Native Stdio Subprocess Daemon   |       |       Declarative WebMCP in Blink  |   |
|   |      (components/perplexity/mcp)   |       |     (HTMLFormElement / WebMCP CDP) |   |
|   +-----------------+------------------+       +-----------------+------------------+   |
|                     |                                            |                      |
|                     v                                            v                      |
|   +------------------------------------+       +------------------------------------+   |
|   | chrome.perplexity.mcp Extension API|       |   CDP Domain: WebMCP               |   |
|   | - getStdioServers()                |       |   - WebMCP.toolsAdded              |   |
|   | - addStdioServer()                 |       |   - WebMCP.invokeTool              |   |
|   | - getTools(serverName)             |       |   - WebMCP.toolInvoked             |   |
|   | - callTool(serverName, tool, args) |       |   - WebMCP.toolResponded           |   |
|   +-----------------+------------------+       +-----------------+------------------+   |
+---------------------|--------------------------------------------|----------------------+
                      |                                            |
                      v                                            v
+------------------------------------+       +------------------------------------+
|  External Developer Tools (zsh)    |       |  Web Page HTML Forms               |
|  - Postgres / SQLite MCP Server    |       |  <form method="tool" name="book">  |
|  - Filesystem MCP Server           |       |    <input name="seat" type="text"> |
|  - Custom CLI Agents               |       |  </form>                           |
+------------------------------------+       +------------------------------------+
```

---

## 2. Native Stdio Daemon Implementation

### C++ Source Structure:
- `components/perplexity/mcp/mcp_stdio_registry.cc`: Manages active subprocess instances, tool registries, and preferences.
- `components/perplexity/mcp/mcp_stdio_client.cc`: Handles JSON-RPC 2.0 frame serialization over POSIX pipes.
- `components/perplexity/mcp/stdio_process_posix.cc`: Spawns child processes using `/bin/zsh`.
- `components/perplexity/mcp/mcp_env_loader_mac.cc`: Extracts user environment variables (`PATH`, `HOME`, `SHELL`) from macOS login environment.
- `chrome/browser/ui/views/perplexity/custom_mcp_server_approval_dialog.cc`: Prompts user before executing arbitrary local shell commands.

### Preferences Persistence:
- `perplexity.mcp.stdio_servers`: Persisted JSON list of configured servers.
- `perplexity.mcp.approved_custom_servers`: Whitelisted custom server hashes.

### Exact Extension API Schema (`chrome.perplexity.mcp`):
Extracted verbatim from `Comet Framework.framework`:

```json
{
  "namespace": "perplexity.mcp",
  "types": [
    {
      "id": "perplexity.mcp.StdioServerStatus",
      "type": "string",
      "enum": ["pending", "running", "stopped", "error"]
    },
    {
      "id": "perplexity.mcp.StdioServer",
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "command": { "type": "string" },
        "env": { "type": "object", "additionalProperties": { "type": "any" } },
        "status": { "$ref": "perplexity.mcp.StdioServerStatus" },
        "tools_count": { "type": "integer" },
        "unparsed_output": { "type": "string" },
        "dxt_name": { "type": "string", "optional": true }
      }
    },
    {
      "id": "perplexity.mcp.Tool",
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "description": { "type": "string" },
        "schema": { "type": "object", "additionalProperties": { "type": "any" } }
      }
    }
  ],
  "functions": [
    {
      "name": "getStdioServers",
      "type": "function",
      "parameters": [],
      "returns_async": { "name": "callback", "parameters": [{ "name": "servers", "type": "array", "items": { "$ref": "perplexity.mcp.StdioServer" } }] }
    },
    {
      "name": "addStdioServer",
      "type": "function",
      "parameters": [
        { "name": "serverName", "type": "string" },
        { "name": "command", "type": "string" },
        { "name": "env", "type": "object", "additionalProperties": { "type": "any" } }
      ],
      "returns_async": { "name": "callback", "parameters": [{ "name": "server", "$ref": "perplexity.mcp.StdioServer" }] }
    },
    {
      "name": "getTools",
      "type": "function",
      "parameters": [{ "name": "serverName", "type": "string" }],
      "returns_async": { "name": "callback", "parameters": [{ "name": "tools", "type": "array", "items": { "$ref": "perplexity.mcp.Tool" } }] }
    },
    {
      "name": "callTool",
      "type": "function",
      "parameters": [
        { "name": "serverName", "type": "string" },
        { "name": "toolName", "type": "string" },
        { "name": "args", "type": "object", "additionalProperties": { "type": "any" } }
      ],
      "returns_async": { "name": "callback", "parameters": [{ "name": "result", "type": "object", "additionalProperties": { "type": "any" } }] }
    },
    {
      "name": "removeStdioServer",
      "type": "function",
      "parameters": [{ "name": "serverName", "type": "string" }],
      "returns_async": { "name": "callback", "parameters": [] }
    }
  ],
  "events": [
    { "name": "onPersistedStdioServersLoaded", "type": "function", "parameters": [] },
    { "name": "onStdioServerAdded", "type": "function", "parameters": [{ "name": "server", "$ref": "perplexity.mcp.StdioServer" }] },
    { "name": "onStdioServerRemoved", "type": "function", "parameters": [{ "name": "serverName", "type": "string" }] },
    { "name": "onStdioServerChanged", "type": "function", "parameters": [{ "name": "serverName", "type": "string" }, { "name": "changes", "$ref": "perplexity.mcp.StdioServerChanges" }] }
  ]
}
```

---

## 3. Declarative WebMCP in Blink

Declarative WebMCP represents a paradigm shift in web scraping and interaction. Instead of having an agent click through text fields and buttons, websites declare native machine interfaces in HTML forms.

### Blink Symbols Identified:
- `void blink::HTMLFormElement::ScheduleDeclarativeWebMCPToolRegistration()`
- `void blink::ModelContext::ExecuteDeclarativeTool(DeclarativeWebMCPTool *, ...)`
- `blink::InspectorWebMCPAgent`
- Features: `kDeclarativeWebmcp`, `kWebMCP`, `kWebMCPDeclarativeFileInput`, `kWebMCPFormAssociatedCustomElements`

### CDP Protocol Methods:
- `WebMCP.enable` / `WebMCP.disable`
- `WebMCP.toolsAdded`: Emits discovered HTML form tools along with JSON Schema derived from form `<input>` attributes (`type`, `required`, `pattern`).
- `WebMCP.toolsRemoved`: Emitted when form elements are detached from the DOM.
- `WebMCP.invokeTool`: Dispatched by the agent to execute a form submission directly.
- `WebMCP.toolResponded`: Returns HTTP response body or DOM mutation resulting from the tool invocation.

---

## 4. Proprietary `chrome.perplexity.*` Native APIs Catalog

| API Namespace | Method / Property | Description |
|---|---|---|
| `chrome.perplexity.mcp` | `getStdioServers`, `addStdioServer`, `callTool` | Native MCP subprocess management. |
| `chrome.perplexity.sidecar` | `open()`, `close()`, `navigate()` | Controls the native macOS floating sidecar assistant panel. |
| `chrome.perplexity.preferences` | `isUrlBlocked()`, `getAllowedDomains()` | Enforces organizational and user privacy policies. |
| `chrome.perplexity.adblock` | `mojom-webui` interfaces | High-performance native content blocker controls. |
