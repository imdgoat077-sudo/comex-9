Key research papers on multi-agent orchestration, grouped by surveys, framework architectures, and evaluation benchmarks:

### Comprehensive Surveys and Taxonomies

*   [Large Language Model based Multi-Agents: A Survey of Progress and Challenges](https://arxiv.org/abs/2402.01680) (Guo et al., 2024, arXiv)
    *   **Focus:** Core multi-agent coordination dimensions: agent profiling, communication mechanisms/topologies, simulation environments (problem-solving vs. world simulation), and capacity growth mechanisms.
*   [Beyond Self-Talk: A Communication-Centric Survey of LLM-Based Multi-Agent Systems](https://arxiv.org/abs/2502.14321) (Yan et al., 2025, *Frontiers of Computer Science*)
    *   **Focus:** Communication-centric taxonomy covering message routing, topological structures, and collective interaction paradigms.
*   [A Survey of Agentic Reasoning for Large Language Models: Towards Recursively Self-Improving and Collective Agents](https://arxiv.org/abs/2601.12538) (Wei et al., 2026, *TMLR*)
    *   **Focus:** Three-dimensional framing spanning foundational reasoning, environment interaction dynamics, and recursive self-improving collective multi-agent architectures.

---

### Foundational Orchestration Frameworks and Execution Protocols

*   [AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155) (Wu et al., 2023, Technical Report)
    *   **Mechanism:** Conversational topology programming. Models orchestration as two-agent chat, sequential chat, and dynamic group chat managed by a `GroupChatManager` with tool use and human-in-the-loop controls.
*   [MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://openreview.net/forum?id=VtmBAGCN7o) (Hong et al., 2023/2024, ICLR 2024)
    *   **Mechanism:** Standard Operating Procedure (SOP) assembly-line orchestration. Implements publish-subscribe shared message pools, role-specific observation filters, and structured intermediate outputs (PRDs, system designs).
*   [ChatDev: Communicative Agents for Software Development](https://arxiv.org/abs/2307.07924) (Qian et al., 2023, ACL 2024)
    *   **Mechanism:** Waterfall software development lifecycle (SDLC) phase coordination. Deconstructs tasks into sequential phases (design, code, test, document) using paired conversational sub-dialogues with reflection loops.
*   [AgentVerse: Facilitating Multi-Agent Collaboration and Exploring Emergent Behaviors in Agents](https://arxiv.org/abs/2308.10848) (Chen et al., 2023/2024, ICLR 2024)
    *   **Mechanism:** Dynamic multi-stage protocol. Coordinates tasks through dynamic expert recruitment, collaborative decision-making, action execution, and evaluation/refinement loops.
*   [VillagerAgent: A Graph-Based Multi-Agent Framework for Coordinating Complex Task Dependencies in Minecraft](https://arxiv.org/abs/2406.05720) (Dong et al., 2024, ACL 2024)
    *   **Mechanism:** Directed Acyclic Graph (DAG) dependency orchestration. Schedules agent execution by mapping prerequisite dependencies and sub-goals onto dynamic causal graphs.

---

### Benchmarks and Evaluation Metrics

*   [OrchBench: Evaluating Multi-Agent Orchestration Plans in Isolation via Deterministic Simulation](https://arxiv.org/abs/2607.25656) (Ren et al., 2026, arXiv)
    *   **Metrics:** Evaluates orchestration plans using DAG simulation against task completion quality, makespan (latency), token cost overhead, and coordination failures across context budgets.
*   [AgentWebBench: Benchmarking Multi-Agent Coordination in Agentic Web](https://arxiv.org/abs/2604.10938) (Zhong et al., 2026, arXiv)
    *   **Metrics:** Benchmarks coordination efficiency, communication overhead, and information exchange between decentralized web-agent providers versus centralized retrieval.
*   [The price of decentralization in managing engineering systems through multi-agent reinforcement learning](https://arxiv.org/abs/2603.11884) (Bhustali et al., 2026, arXiv)
    *   **Metrics:** Quantifies performance degradation and coordination overhead incurred when shifting from centralized controllers to decentralized multi-agent policies.
*   [CalBench: Evaluating Coordination-Privacy Trade-offs in Multi-Agent LLMs](https://arxiv.org/abs/2605.09823) (Zou et al., 2026, arXiv)
    *   **Metrics:** Measures negotiation overhead, communication failure modes, and privacy trade-offs in delegate agent-to-agent negotiations.

---

### Missing Information and Limitations

*   Full-text PDF data extraction was not performed; granular sub-taxonomies (e.g., exact mathematical formulations of centralized vs. decentralized routing graphs) and empirical numerical tables for `AgentWebBench` and `The price of decentralization` were not extracted beyond their abstracts and metadata.
*   External literature databases (Google Scholar, Papers with Code) were not reached due to browser step limits.