# Comet Browser: Deep Reverse-Engineering & Architecture Deliverables

## Mission Overview
This repository contains the complete technical deliverables resulting from an exhaustive reverse-engineering investigation of the locally installed **Perplexity Comet Browser** (`ai.perplexity.comet`, Chromium fork 154.0.8037.179 arm64 on macOS).

The investigation analyzed:
1. Native Chromium C++ engine modifications and framework binaries (`Comet Framework.framework`).
2. Bundled and unpacked Chrome Extensions (`comet-agent`, `Comet Core`, `Comet Web Resources`).
3. Model Context Protocol (MCP) implementations (native C++ stdio subprocess daemon and declarative WebMCP in Blink).
4. Dual-tier perception and Anthropic Computer-Use action batching pipelines.

The ultimate objective of this documentation is to guide the independent implementation of a comparably capable browser automation architecture for **Comex** (Electron 43.4.0 + FastAPI daemon + CDP port 9222).

---

## Deliverables Catalog

| File | Subsystem / Focus | Description |
|---|---|---|
| [`01_artifact_inventory.csv`](./01_artifact_inventory.csv) | Full Application Catalog | 1,655 cataloged files across app bundles, frameworks, and extensions. |
| [`evidence_index.json`](./evidence_index.json) | Rigorous Evidence Mapping | Machine-readable index mapping core technical claims to symbol addresses and confidence levels. |
| [`02_module_dependency_map.md`](./02_module_dependency_map.md) | Extension Topology | Component relationships, IPC communication channels, and entry points. |
| [`03_agent_execution_lifecycle.md`](./03_agent_execution_lifecycle.md) | Lifecycle & State Machine | Complete end-to-end trace from initial user prompt to task teardown. |
| [`04_perception_pipeline.md`](./04_perception_pipeline.md) | Vision & DOM Synthesis | Dual-tier hybrid perception (`gN`), CDP AXTree + DOMSnapshot compiler. |
| [`05_action_engine.md`](./05_action_engine.md) | Input & Action Execution | Full catalog of actions, high-fidelity clipboard typing (`uP`), and select tracking. |
| [`06_coordinate_geometry.md`](./06_coordinate_geometry.md) | Mathematics & Scaling | Viewport math, DPR adjustment, drift abort gate (`_P`), worked numerical examples. |
| [`07_batching_and_waiting.md`](./07_batching_and_waiting.md) | Batching & Heuristics | `ComputerBatch` loop, jitter delays, and smart wait coordinator (`oN` / `sN`). |
| [`08_errors_recovery_and_cancellation.md`](./08_errors_recovery_and_cancellation.md) | Recovery & Self-Healing | Self-healing RPC dispatcher (`class dM`), re-attachment, and reload recovery. |
| [`09_worker_orchestration.md`](./09_worker_orchestration.md) | Multi-Tab Subagents | Subagent delegation (`CreateSubagent`), hidden tab groups (`pM`). |
| [`10_mcp_webmcp_and_native_apis.md`](./10_mcp_webmcp_and_native_apis.md) | MCP & WebMCP Protocols | C++ Stdio MCP daemon, Blink Declarative WebMCP, and `chrome.perplexity.*` APIs. |
| [`11_streaming_and_ui_integration.md`](./11_streaming_and_ui_integration.md) | Streaming & UI Integration | React `StreamMiddlewares`, ASI WebSocket, glowing HUD overlay (`content.js`). |
| [`12_security_and_execution_boundaries.md`](./12_security_and_execution_boundaries.md) | Sandboxing & Security | Seatbelt sandbox, PartitionAlloc (`libaperitif.dylib`), policy guardrails. |
| [`13_capability_matrix.md`](./13_capability_matrix.md) | 10-Category Web Assessment | Stress-test assessment across SPAs, rich text, canvas, tables, Wordle, etc. |
| [`14_unresolved_questions.md`](./14_unresolved_questions.md) | Unknowns & Probes | Cloud-resident components and minimal verification experiments. |
| [`15_master_architecture_specification.md`](./15_master_architecture_specification.md) | Comex Implementation Guide | Architectural blueprint translating Comet's engine into Electron + FastAPI. |
| [`16_extracted_source_and_disassembly.md`](./16_extracted_source_and_disassembly.md) | Code & Disassembly | Annotated extracted source code for `class iP`, `uP`, `vP`, `bP`, `gN`, `dM`, and MCP schemas. |

---

## Evidence Rating Scale
- **Level A**: Directly observed and extracted from installed binaries, JavaScript bundles, or manifest schemas.
- **Level B**: High-confidence technical inference supported by multiple correlated source artifacts.
- **Level C**: Prior architectural claim verified against local file footprints.
- **Level D**: Unknown or unverified; requires live cloud telemetry or remote server probing.
