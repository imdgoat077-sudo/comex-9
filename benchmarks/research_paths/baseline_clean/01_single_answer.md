Key research papers on multi-agent orchestration, categorized by architectural paradigm and core challenge:

#### 1. Foundational Orchestration Frameworks & Architectures
- **[AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155)** (Wu et al., 2023)
  - *Core Concept:* Multi-agent conversational orchestration. Formulates workflows as programmable, customizable multi-agent chat topologies (sequential, hierarchical, dynamic group chat).
- **[MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352)** (Hong et al., 2023)
  - *Core Concept:* Standard Operating Procedure (SOP) driven orchestration. Enforces structured communication protocols, schemas, and role specializations to eliminate cascading conversational drift.
- **[ChatDev: Communicative Agents for Software Development](https://arxiv.org/abs/2307.07924)** (Qian et al., 2023)
  - *Core Concept:* Waterfall/phase-based chain coordination. Employs chat chains with reciprocal peer review and sub-task handoffs across distinct lifecycle stages.

#### 2. Dynamic Routing, Topology & Task Allocation
- **[Dynamic LLM-Agent Network: An LLM-agent Collaboration Framework with Agent Team Optimization](https://arxiv.org/abs/2310.02170)** (DyLAN; Liu et al., 2023)
  - *Core Concept:* Runtime topology optimization. Evaluates individual agent contributions using an LLM-based rating mechanism and dynamically activates, prunes, or re-routes agents per task layer.
- **[SquidAgent: Parallelize Wisely, Coordinate Efficiently](https://arxiv.org/abs/2410.08647)** (Lin et al., NeurIPS 2024)
  - *Core Concept:* Hybrid sequential-parallel execution. Optimizes task dependency graphs to execute non-dependent reasoning branches in parallel while maintaining strict synchronization barriers.
- **[Agent Q-Mix: Selecting the Right Action for LLM Multi-Agent Systems through Reinforcement Learning](https://arxiv.org/abs/2404.00344)** (Jiang et al., 2024)
  - *Core Concept:* Policy-guided orchestration. Combines value-decomposition RL with LLM multi-agent systems to optimize action selection and agent routing over discrete execution paths.

#### 3. Consensus, Debate & Collective Reasoning
- **[Improving Factuality and Reasoning in Language Models through Multiagent Debate](https://arxiv.org/abs/2305.14325)** (Du et al., 2023)
  - *Core Concept:* Multi-agent debate orchestration. Multiple instances evaluate and critique divergent answers over rounds to reach consensus, significantly suppressing hallucinations.
- **[Exchange-of-Thought: Enhancing Large Language Model Capabilities through Cross-Model Communication](https://arxiv.org/abs/2312.01823)** (Wang et al., 2023)
  - *Core Concept:* Distributed communication topology. Evaluates peer-to-peer, hub-and-spoke, and hierarchical message-passing topologies for collective reasoning tasks.

#### 4. System-Level Runtimes & Infrastructure
- **[AIOS: LLM Agent Operating System](https://arxiv.org/abs/2403.16971)** (Mei et al., 2024)
  - *Core Concept:* OS-level orchestration. Implements scheduling, context isolation, tool/agent memory allocation, and access control for concurrent multi-agent systems.
- **[Know the Shape, Find the Fault: Topology-Conditioned Diagnosis of Multi-Agent LLM Failures](https://arxiv.org/abs/2410.10126)** (Liu et al., 2024)
  - *Core Concept:* Failure modes in graph orchestration. Analyzes error propagation patterns across pipeline, tree, cycle, and star topologies.

#### 5. Comprehensive Surveys
- **[A Survey on Large Language Model based Autonomous Agents](https://arxiv.org/abs/2308.11432)** (Wang et al., 2023)
  - Sections covering agent architectures, social interactions, and multi-agent coordination paradigms.
- **[The Rise and Potential of Large Language Model Based Agents: A Survey](https://arxiv.org/abs/2309.07864)** (Xi et al., 2023)
  - Structural analysis of static workflows vs. adaptive cooperative/competitive orchestrations.