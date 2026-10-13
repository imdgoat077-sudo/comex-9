Top research papers on multi-agent orchestration, grouped by surveys, foundational frameworks, and benchmark/failure evaluations:

### 1. Surveys and Taxonomies
- [Large language model based multi-agents: A survey of progress and challenges](https://arxiv.org/abs/2402.01680) (Guo et al., 2024, arXiv:2402.01680): Classifies multi-agent architectures, agent profiling, coordination mechanisms, and communication paradigms.
- [Multi-agent collaboration mechanisms: A survey of LLMs](https://arxiv.org/abs/2501.06322) (Tran et al., 2025, arXiv:2501.06322): Reviews coordination frameworks, collaborative mechanisms, and orchestration dynamics across LLM systems.
- [A survey on LLM-based multi-agent systems: workflow, infrastructure, and challenges](https://link.springer.com/article/10.1007/s44336-024-00009-2) (Li et al., 2024, *Vicinagearth*, Springer): Focuses on orchestration workflows, information exchange, infrastructure models, and action coordination.
- [Beyond self-talk: A communication-centric survey of LLM-based multi-agent systems](https://arxiv.org/abs/2502.14321) (Yan et al., 2025, arXiv:2502.14321): Evaluates multi-agent topologies, message-passing structures, protocol designs, and task execution workflows.
- [A survey of multi-AI agent collaboration: Theories, technologies and applications](https://dl.acm.org/doi/abs/10.1145/3745238.3745531) (Zhang et al., 2025, ACM): Covers theoretical coordination foundations, multimodal integration, and multi-agent task execution.

### 2. Foundational Orchestration Frameworks
- [AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155) (Wu et al., 2023, arXiv:2308.08155): Introduces conversable agent architecture with dynamic routing, group chat orchestration, and code/natural-language-driven control topologies across LLMs, tools, and humans.
- [ChatDev: Communicative Agents for Software Development](https://arxiv.org/abs/2307.07924) (Qian et al., 2023/2024, ACL 2024 / arXiv:2307.07924): Formulates a communicative phase-gated execution graph (design, coding, testing) using multi-agent role-playing dialogues.

### 3. Benchmarks, Coordination Overhead, and Failure Attribution
- [Error-Propagation Modeling for Failure Attribution in LLM-Based Multi-Agent Systems](https://arxiv.org/abs/2610.11600) (Liao et al., 2026, arXiv:2610.11600): Evaluates failure cascades on the Who&When benchmark using the EMFA framework with candidate screening and counterfactual verification (+3.45% and +4.40% recovery attribution).
- [EDGE: Error Dependency Graph-Guided Multi-Error Attribution in Multi-Agent LLM Systems](https://arxiv.org/abs/2609.01360) (Hou et al., 2026, EMNLP 2026 / arXiv:2609.01360): Evaluates multi-error dependencies and compound execution failures across multi-agent graphs.
- [DCFA: Dual-view Causal-inspired Attribution for Failure Reasoning in LLM-based Multi-agent Systems](https://arxiv.org/abs/2609.04749) (Wang et al., 2026, arXiv:2609.04749): Evaluates coordination overhead and causal attribution, disentangling task-flow dependencies from inter-agent communications.
- [From Investigation Failures to Reliable SOC Agents: Understanding and Improving LLM-Based Alert Triage](https://arxiv.org/abs/2610.10608) (Tsegai et al., 2026, arXiv:2610.10608): Benchmarks complex orchestration on ALERT-BENCH (1,247 telemetry alerts), analyzing coordination failures and evidence omission in multi-agent loops.
- [Agent4RE: A Self-Refining Multi-agent Framework for End-to-End Software Requirements Engineering and Benchmarking](https://arxiv.org/abs/2610.10628) (Tang et al., 2026, ASE@POVC 2026 / arXiv:2610.10628): Evaluates structured iterative consensus mechanisms versus basic multi-agent prompting on the E2E Requirements Engineering Benchmark.

### Missing and Uncertain Information
- Framework coverage is incomplete: other standard graph-centric multi-agent architectures (such as MetaGPT, LangGraph, or CAMEL) were not retrieved due to search limit constraints.
- Full PDF metrics and exact taxonomy sub-branches for Springer and ACM survey papers, as well as baseline metric tables for EDGE and DCFA, were not extracted because agents only accessed abstract pages and metadata. Platforms like OpenReview, Semantic Scholar, and Papers with Code were not queried.