#### Foundational Papers & Frameworks

- **[Multi-Agent Collaboration Mechanisms: A Survey of LLMs](https://arxiv.org/abs/2501.06322)**
  - **Focus:** Comprehensive taxonomy of multi-agent LLM systems.
  - **Key Contributions:** Analyzes collaboration topologies, communication protocols, dynamic role assignment, and centralized vs. decentralized orchestration paradigms.

- **[Multi-Agent Collaboration via Evolving Orchestration](https://proceedings.neurips.cc/paper_files/paper/2025/hash/f1320d2e2842169c6fc89dcbd80e94d0-Abstract-Conference.html)** *(NeurIPS)*
  - **Focus:** Dynamic and self-adapting coordination graphs.
  - **Key Contributions:** Introduces self-evolving orchestration where communication links, agent roles, and task routing dynamically mutate based on intermediate reasoning steps.

- **[AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155)** *(Wu et al., Microsoft Research)*
  - **Focus:** Conversational multi-agent orchestration.
  - **Key Contributions:** Defines multi-agent workflows as structured multi-turn conversations between customizable, tool-enabled agents and human proxies.

- **[MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352)** *(Hong et al.)*
  - **Focus:** SOP-driven (Standard Operating Procedure) multi-agent software engineering.
  - **Key Contributions:** Enforces structured communication pipelines, role division (architect, engineer, QA), and publish-subscribe message pools to avoid communication collapse.

#### Advanced Architectures & Topologies

- **[HALO: Hierarchical Autonomous Logic-Oriented Orchestration for Multi-Agent LLM Systems](https://arxiv.org/abs/2505.13516)**
  - **Focus:** Multi-tiered hierarchical control.
  - **Key Contributions:** Implements a three-tier design: high-level task decomposition agents, mid-level role-design agents, and low-level specialized inference agents.

- **[AdaptOrch: Task-Adaptive Multi-Agent Orchestration in the Era of LLM Performance Convergence](https://arxiv.org/abs/2602.16873)**
  - **Focus:** Adaptive topology selection.
  - **Key Contributions:** Demonstrates that orchestration structure (graph topology, verification loops) impacts complex reasoning performance more significantly than raw model parameter size.

- **[Beyond the Strongest LLM: Multi-Turn Multi-Agent Orchestration vs. Single LLMs on Benchmarks](https://arxiv.org/abs/2509.23537)**
  - **Focus:** Quantitative limits and scaling laws of multi-agent debate and consensus.
  - **Key Contributions:** Evaluates trade-offs between context window bloat, cascading errors, token overhead, and accuracy gains across multi-turn orchestrated pipelines.

- **[SALLMA: A Software Architecture for LLM-Based Multi-Agent Systems](https://ieeexplore.ieee.org/abstract/document/11029425/)** *(IEEE/ACM)*
  - **Focus:** System design and software engineering patterns for multi-agent reliability.
  - **Key Contributions:** Focuses on production fault tolerance, agent state recovery, backpressure handling, and modular orchestrator design.