Key research papers on multi-agent orchestration, categorized by foundational architectures, dynamic orchestration paradigms, and surveys:

#### Foundational Orchestration Frameworks
- **[AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155)** (Wu et al., 2023)
  - **Contribution:** Introduces conversable, customizable agents that coordinate using multi-agent conversation patterns (static, dynamic, hierarchical, human-in-the-loop).
  - **Key Focus:** Unified messaging layer for orchestrating tool use, code execution, and agent cooperation.

- **[ChatDev: Communicative Agents for Software Development](https://aclanthology.org/2024.acl-long.810/)** (Qian et al., ACL 2024)
  - **Contribution:** Formulates the "chat chain" model for sequential and iterative waterfall orchestration across role-specialized agents (designers, coders, testers).
  - **Key Focus:** Structured role-play orchestration and communicative de-hallucination.

- **[MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352)** (Hong et al., ICLR 2024)
  - **Contribution:** Standard Operating Procedure (SOP) based orchestration. Encodes human workflow SOPs into structured prompt schemas and publish-subscribe message pools.
  - **Key Focus:** Reducing cascading error loops through structured artifacts and communication protocols.

---

#### Dynamic & Evolving Orchestration
- **[Multi-Agent Collaboration via Evolving Orchestration](https://proceedings.neurips.cc/paper_files/paper/2025/hash/f1320d2e2842169c6fc89dcbd80e94d0-Abstract-Conference.html)** (Dang et al., NeurIPS)
  - **Contribution:** Shifts from static agent topologies to an evolving orchestration mechanism where execution paths, sub-agents, and communication graphs adapt dynamically during reasoning.
  - **Key Focus:** Autonomous restructuring of agent topologies based on task feedback.

- **[HALO: Hierarchical Autonomous Logic-Oriented Orchestration for Multi-Agent LLM Systems](https://arxiv.org/abs/2505.13516)** (Hou et al., 2025)
  - **Contribution:** Three-tier hierarchy: top-level task decomposition agent, mid-level role-design agents (on-demand agent instantiation), and low-level task execution/inference agents.
  - **Key Focus:** Dynamic agent instantiation and hierarchical routing.

- **[Beyond the Strongest LLM: Multi-Turn Multi-Agent Orchestration vs. Single LLMs on Benchmarks](https://arxiv.org/abs/2509.23537)** (Tian et al., 2025)
  - **Contribution:** Empirical study benchmarking multi-agent orchestration structures (centralized controller vs. peer debate vs. hierarchical delegation) against single frontier models.
  - **Key Focus:** Quantitative trade-offs between coordination overhead, token cost, and accuracy gains.

---

#### Architecture Taxonomy & Comprehensive Surveys
- **[Architectural Design, Not Only Model Intelligence, Governs Multi-Agent LLM Performance](https://arxiv.org/abs/2602.03128)** (Orogat, Rostam, Mansour)
  - **Contribution:** Architectural taxonomy systematically comparing multi-agent topologies (centralized, decentralized, pipeline, tree-hierarchical) and isolation mechanisms.
  - **Key Focus:** Proves that orchestration topology and protocol design often matter more than underlying parameter scale.

- **[Multi-Agent Collaboration Mechanisms: A Survey of LLMs](https://arxiv.org/abs/2501.06322)** (Tran et al., 2025)
  - **Contribution:** Comprehensive review covering coordination, orchestration topologies (centralized controllers, graph workflows, swarm dynamics), memory sharing, and failure modes.
  - **Key Focus:** Taxonomy of communication protocols and orchestration patterns across state-of-the-art frameworks.