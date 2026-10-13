# 14 — Unresolved Questions & Minimal Verification Probes

## 1. Unresolved Technical Questions

While the reverse-engineering mission successfully recovered the complete client-side architecture, the following areas reside on Perplexity's cloud infrastructure and cannot be directly observed from local client artifacts:

### Question 1: Backend System Prompting & Action Grammar
- **Uncertainty**: Does Perplexity feed Anthropic's exact default Computer-Use tool schema, or does it inject a custom system prompt converting natural language thoughts into the composite `ComputerBatch` payload?
- **Confidence Rating**: Level B (Inference from client payload schemas).

### Question 2: Autonomous Subagent Spawning Threshold
- **Uncertainty**: What specific heuristics or entropy scores on the backend trigger `entropy_request_content` to spawn parallel subagents versus executing actions sequentially?
- **Confidence Rating**: Level C (Observed in `StreamMiddlewares`, but decision model resides on backend).

### Question 3: Declarative WebMCP Adoption & Server Verification
- **Uncertainty**: How does the Blink rendering engine verify cryptographically signed WebMCP tools on public websites to prevent adversarial prompt injection?
- **Confidence Rating**: Level D (Symbols present in `Comet Framework`, but public production sites using Declarative WebMCP are not yet cataloged).

---

## 2. Minimal Verification Probes

To resolve these questions empirically without violating read-only boundaries, the following non-invasive test scripts can be executed against a live test harness:

### Probe 1: Inspecting Live ComputerBatch Prompts via CDP Interception
Configure a local HTTP/WebSocket proxy on port 8080 and launch Comet with `--proxy-server=http://localhost:8080`. Log outgoing WebSocket frames to capture the exact system prompt and tool definitions transmitted during task initialization.

### Probe 2: Testing Declarative WebMCP Registration
Host a minimal local HTML page containing:
```html
<form method="tool" name="test_calculator" action="/calc">
  <input name="a" type="number" required>
  <input name="b" type="number" required>
  <button type="submit">Calculate</button>
</form>
```
Connect via CDP to the tab and verify whether `WebMCP.toolsAdded` fires with the parsed JSON schema.
