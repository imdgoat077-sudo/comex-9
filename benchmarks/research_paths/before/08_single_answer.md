#### Foundational Frameworks

- **[AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155)**
  * **Authors:** Qingyun Wu, Gagan Bansal, Jieyu Zhang, et al. (Microsoft Research)
  * **Focus:** Introduces conversational multi-agent orchestration. Uses customizable, conversable agents that integrate LLMs, human inputs, and tool-execution environments via structured multi-turn message passing.
  * **Relevance:** The baseline architecture for conversational multi-agent workflows.

- **[MetaGPT: Meta Programming for a Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352)** *(ICLR 2024)*
  * **Authors:** Sirui Hong, Mingchen Zhuge, Jonathan Chen, et al.
  * **Focus:** Introduces Standard Operating Procedures (SOPs) into multi-agent systems. Formulates agent coordination via structured software engineering artifacts (PRDs, architecture diagrams, code reviews) rather than unstructured dialogues.
  * **Relevance:** Solves agent derailment and cascade errors through structured communication protocols.

---

#### Advanced Dynamic & Adaptive Orchestration

- **[Multi-Agent Collaboration via Evolving Orchestration](https://proceedings.neurips.cc/paper_files/paper/2025/hash/f1320d2e2842169c6fc89dcbd80e94d0-Abstract-Conference.html)** *(NeurIPS)*
  * **Authors:** Y. Dang, C. Qian, X. Luo, et al.
  * **Focus:** Dynamic orchestration graphs where agent interaction topologies evolve during runtime based on feedback and intermediate sub-goal completion.
  * **Relevance:** Addresses rigid static agent networks by adapting communication routing dynamically.

- **[HALO: Hierarchical Autonomous Logic-Oriented Orchestration for Multi-Agent LLM Systems](https://arxiv.org/abs/2505.13516)**
  * **Authors:** Z. Hou, J. Tang, Y. Wang
  * **Focus:** Three-tier hierarchical orchestration: high-level task decomposition agents, mid-level role-design agents (on-the-fly persona instantiation), and low-level task execution agents.
  * **Relevance:** Mitigates overhead and context saturation in large-scale multi-step tasks.

- **[Navigating Complexity: Orchestrated Problem Solving with Multi-Agent LLMs](https://arxiv.org/abs/2402.16713)**
  * **Authors:** S. Rasal, E. J. Hauer
  * **Focus:** Orchestrator-worker pattern formalization, tracking error handling, context handoffs, and feedback loops across heterogeneous agent networks.

---

#### Architecture, Benchmarks, & Surveys

- **[Multi-Agent Collaboration Mechanisms: A Survey of LLMs](https://arxiv.org/abs/2501.06322)**
  * **Authors:** K. T. Tran, D. Dao, M. D. Nguyen, Q. V. Pham, et al.
  * **Focus:** Taxonomy of coordination, planning, and communication protocols (centralized vs. decentralized, debate vs. cooperative consensus).
  * **Relevance:** Comprehensive primer on theoretical models behind LLM orchestration.

- **[Beyond the Strongest LLM: Multi-Turn Multi-Agent Orchestration vs. Single LLMs on Benchmarks](https://arxiv.org/abs/2509.23537)**
  * **Authors:** A. X. Tian, R. Zhang, J. Tang, Y. M. Cho, et al.
  * **Focus:** Quantitative benchmark evaluating when multi-agent orchestration outperforms state-of-the-art single frontier models versus when communication overhead causes degradation.