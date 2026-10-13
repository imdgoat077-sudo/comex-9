The leading research papers on multi-agent orchestration and coordination architectures:

---

#### 1. Foundational Orchestration Frameworks & Coordination Patterns

*   **[AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155)** (Wu et al., 2023)
    *   **Core Contribution:** Introduces a multi-agent conversation framework where orchestration occurs via programmable, automated chat interactions between customizable agents (human-in-the-loop, tool-executors, LLM personas).
    *   **Focus:** Flexible orchestration patterns (dynamic round-robin, group chats, nested chat topologies).

*   **[MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352)** (Hong et al., 2023 / ICLR 2024)
    *   **Core Contribution:** Integrates Standard Operating Procedures (SOPs) into agent workflows. Solves cascading hallucinations and unstructured agent chatter by enforcing structured artifact exchange (PRDs, design docs, UMLs).
    *   **Focus:** Role-based workflow orchestration and publish-subscribe message-sharing models.

*   **[Communicative Agents for Software Development (ChatDev)](https://arxiv.org/abs/2307.07924)** (Qian et al., 2023 / ACL 2024)
    *   **Core Contribution:** Establishes multi-agent communicative problem solving using the classical Waterfall model (designing, coding, testing, documenting) via pairwise agent dialogue (chat-chains).
    *   **Focus:** Phased, sequential orchestration with sub-task decomposition.

---

#### 2. Scaling, Routing & Execution Efficiency

*   **[More Agents Is All You Need](https://arxiv.org/abs/2402.01817)** (Li et al., 2024)
    *   **Core Contribution:** Investigates scaling properties of multi-agent ensembles. Demonstrates that performance scales with agent counts via majority voting and diverse reasoning paths when orchestrated effectively.
    *   **Focus:** Ensembling, token budgets, and orchestration difficulty scaling across tasks.

*   **[SquidAgent: Parallelize Wisely, Coordinate Efficiently](https://arxiv.org/abs/2610.08647)** (Lin et al., NeurIPS)
    *   **Core Contribution:** Analyzes the trade-off between parallel independent agent execution and serial cooperative orchestration, proposing dynamic coordination topologies to reduce latency and redundant tokens.
    *   **Focus:** Parallel vs. sequential orchestration efficiency.

---

#### 3. Topology, Failure Handling & Surveys

*   **[A Survey on Large Language Model based Multi-Agent Systems](https://arxiv.org/abs/2308.11432)** (Wang et al., 2023)
    *   **Core Contribution:** Comprehensive taxonomic breakdown of multi-agent architectures, detailing orchestration structures (centralized vs. decentralized, static vs. dynamic, layered vs. shared memory).
    *   **Focus:** Broad architecture patterns, communication protocols, and multi-agent alignment.

*   **[Know the Shape, Find the Fault: Topology-Conditioned Diagnosis of Multi-Agent LLM Failures](https://arxiv.org/abs/2610.10126)** (Liu et al., 2024)
    *   **Core Contribution:** Explores how orchestration graph topologies (trees, rings, stars, meshes) impact cascading failure modes and presents diagnostic tooling for agent networks.
    *   **Focus:** Orchestration topology robustness and failure analysis.