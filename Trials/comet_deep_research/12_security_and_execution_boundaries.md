# 12 — Security Model, Sandboxing & Execution Boundaries

## 1. Multi-Layered Defense-in-Depth

Granting an autonomous AI agent control over a browser environment entails significant security risks: prompt injection attacks, unauthorized financial transactions, credential harvesting, and local shell compromise.

Comet enforces security through **five strict isolation boundaries**:

```
+-------------------------------------------------------------------------+
| Layer 1: OS-Level Seatbelt Sandbox & Allocator Hardening                |
| - libaperitif.dylib: PartitionAlloc malloc zone hook                    |
| - macOS Seatbelt Sandbox profile (com.apple.security.app-sandbox)       |
+------------------------------------+------------------------------------+
                                     |
+------------------------------------v------------------------------------+
| Layer 2: Organizational Policy Enforcement                             |
| - managed_schema.json: BlockedDomains, OrganizationUUID                 |
| - CrowdStrike Zero Trust Assessment (ZTA) integration                   |
+------------------------------------+------------------------------------+
                                     |
+------------------------------------v------------------------------------+
| Layer 3: Internal Page & Scheme Isolation                              |
| - Nj.isInternalPage: Rejects chrome://, devtools://, chrome-extension://|
+------------------------------------+------------------------------------+
                                     |
+------------------------------------v------------------------------------+
| Layer 4: Human-in-the-Loop Confirmation Gates                           |
| - WAIT_FOR_BROWSER_AGENT_CONFIRMATION: Form submissions & checkouts     |
| - Options: ALLOW_ONCE, ALWAYS_ALLOW, SKIP                               |
+------------------------------------+------------------------------------+
                                     |
+------------------------------------v------------------------------------+
| Layer 5: Native MCP Subprocess Authorization                            |
| - custom_mcp_server_approval_dialog.cc: Explicit user consent for zsh   |
| - Strict regex validation on server names: ^[a-zA-Z0-9_-]+$             |
+-------------------------------------------------------------------------+
```

---

## 2. macOS Seatbelt Sandboxing & `libaperitif.dylib`

Located at:
`/Applications/Comet.app/Contents/Frameworks/Comet Framework.framework/Versions/Current/Libraries/libaperitif.dylib`

### Dynamic Library Analysis:
- Implements `_AperitifCheckInitialized` and `DelegatingDefaultZoneForPartitionAlloc`.
- Intercepts system `malloc` zones on macOS to force helper processes to allocate heap memory exclusively through Chromium's hardened `PartitionAlloc` allocator.
- Mitigates heap-use-after-free and buffer overflow exploits originating from adversarial web content.

---

## 3. Policy & Domain Guardrails (`managed_schema.json`)

Comet embeds managed administrative schemas allowing enterprise IT administrators to restrict agent capabilities via MDM (Mobile Device Management):

```json
{
  "type": "object",
  "properties": {
    "OrganizationUUID": {
      "type": "string",
      "description": "Unique identifier of the managing enterprise organization"
    },
    "BlockedDomains": {
      "type": "array",
      "items": { "type": "string" },
      "description": "List of domains where Comet Agent execution and screenshots are strictly blocked"
    },
    "AllowCustomMCPServers": {
      "type": "boolean",
      "description": "Controls whether users can register local shell MCP servers"
    }
  }
}
```

In `background.js`:
```javascript
if (await this.deps.preferences.isUrlBlocked(targetUrl)) {
  throw new lM("This url is restricted by user or system. You cannot navigate to this url.");
}
```

---

## 4. Human-in-the-Loop Confirmation Gate

To prevent catastrophic unauthorized actions (e.g. deleting an email, completing a credit card checkout), Comet pauses execution and presents a modal prompt:
- Message type: `WAIT_FOR_BROWSER_AGENT_CONFIRMATION`
- Action choices:
  - `ALLOW_ONCE`: Authorizes the single pending action.
  - `ALWAYS_ALLOW`: Whitelists the domain for the remainder of the session (`handleAlwaysAllowBrowserAgent`).
  - `SKIP`: Discards the action and signals the model to find an alternative route.
