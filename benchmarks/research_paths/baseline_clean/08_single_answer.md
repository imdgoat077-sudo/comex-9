#### Foundational Architecture & Frameworks

* **[AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155)** (Wu et al., Microsoft Research)
  * **Core Focus:** Multi-agent conversation programming.
  * **Mechanism:** Defines agents as conversational entities (`ConversableAgent`) capable of exchanging messages with humans, tools, and other models. Supports automated group chat managers, static/dynamic graph transitions, and event-driven orchestration.

* **[MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352)** (Hong et al., ICLR 2024)
  * **Core Focus:** SOP-driven (Standard Operating Procedure) agent coordination.
  * **Mechanism:** Enforces structured outputs and role assignments (Product Manager, Architect, Engineer) via publish-subscribe message sharing, eliminating multi-agent chat noise and coordination drift.

* **[ChatDev: Communicative Agents for Software Development](https://arxiv.org/abs/2307.07924)** (Qian et al., ACL 2024)
  * **Core Focus:** Multi-agent role-play in staged workflows.
  * **Mechanism:** Chains role-playing dialogues across sequential phases (designing, coding, testing, documenting) using chat chains and sub-task decomposing mechanisms.

* **[AgentVerse: Facilitating Multi-Agent Collaboration and Exploring Emergent Behaviors](https://arxiv.org/abs/2308.10848)** (Chen et al., ICLR 2024)
  * **Core Focus:** Dynamic recruitment and flexible network orchestration.
  * **Mechanism:** Breaks execution into four modular stages: expert recruitment, collaborative planning, parallel execution, and evaluation/feedback loops.

---

#### Dynamic Topologies & Routing Orchestration

* **[Dynamic LLM-Agent Network (DyLAN)](https://arxiv.org/abs/2310.02170)** (Liu et al.)
  * **Core Focus:** Adaptive agent network routing.
  * **Mechanism:** Constructs a dynamic communication architecture where agents score peer contributions and prune unhelpful nodes across iterative reasoning rounds.

* **[More Agents Is All You Need](https://arxiv.org/abs/2402.05120)** (Li et al.)
  * **Core Focus:** Scaling dynamics in multi-agent orchestration.
  * **Mechanism:** Analyzes agent count scaling versus single-agent compute, demonstrating when sampling-and-voting ensembles outperform complex communicative topologies.

* **[SquidAgent: Parallelize Wisely, Coordinate Efficiently](https://arxiv.org/abs/2610.08647)** (Lin et al., NeurIPS 2024)
  * **Core Focus:** Parallel execution and latency reduction in agent swarms.
  * **Mechanism:** Balances sequential dependency graphs with asynchronous parallel execution to minimize token overhead and pipeline stalls.

---

#### Systematic Surveys & Taxonomies

* **[A Survey on Large Language Model based Autonomous Agents](https://arxiv.org/abs/2308.11432)** (Wang et al., Frontiers of Computer Science)
  * **Core Focus:** Structural taxonomy of agent components: profile, memory, planning, and action systems.

* **[A Survey on Multi-Agent Systems in the Era of Large Language Models](https://arxiv.org/abs/2404.05364)** (Cheng et al.)
  * **Core Focus:** Classification of multi-agent topologies (centralized, decentralized, hierarchical), coordination protocols, and failure modes.