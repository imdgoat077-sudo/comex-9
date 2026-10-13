Key research papers on multi-agent orchestration:

#### Foundational Orchestration Frameworks & Architectures
- **[AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155)** (Wu et al., 2023)
  - **Contribution:** Introduces conversable agents capable of orchestrating complex workflows via programmatic and natural-language message flows, human-in-the-loop controls, and automated code execution.
  - **Significance:** Standard reference architecture for conversational multi-agent coordination.

- **[MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352)** (Hong et al., 2023)
  - **Contribution:** Encodes Standard Operating Procedures (SOPs) into prompt sequences, role assignments (Product Manager, Architect, Engineer), and structured publish-subscribe message pools.
  - **Significance:** Reduces hallucination cascades and coordination drift in complex software engineering pipelines.

- **[ChatDev: Communicative Agents for Software Development](https://arxiv.org/abs/2307.07924)** (Qian et al., 2023)
  - **Contribution:** Proposes the ChatChain mechanism, breaking down software lifecycles into atomic multi-agent sub-tasks using role-playing and communicative de-biasing.
  - **Significance:** Demonstrates structured phase-based agent handover and peer-review loops.

#### Coordination Topologies & Communication Mechanics
- **[More Agents Is All You Need](https://arxiv.org/abs/2402.05120)** (Li et al., 2024)
  - **Contribution:** Analyzes scaling properties of multi-agent ensembles, showing performance gains scale with ensemble size via majority voting and dynamic task-difficulty routing.
  - **Significance:** Establishes empirical trade-offs between orchestration complexity, inference token overhead, and accuracy.

- **[DyLAN: Dynamic LLM-Agent Network for Efficient Multi-Agent Collaboration](https://arxiv.org/abs/2310.02170)** (Liu et al., 2023)
  - **Contribution:** Implements dynamic layered networks that score agent contributions and prune inactive or low-performing agents during task execution.
  - **Significance:** Solves communication redundancy and inference cost bottlenecks in multi-round multi-agent graphs.

- **[Magentic-One: A Generalist High-Performing Multi-Agent System for Solving Complex Tasks](https://arxiv.org/abs/2411.04468)** (Fourney et al., Microsoft Research, 2024)
  - **Contribution:** Implements a centralized **Orchestrator** agent maintaining a ledger and task progress state, directing specialist sub-agents (WebSurfer, FileSurfer, Coder, Terminal).
  - **Significance:** Provides a reference pattern for centralized task-plan management, replanning, and error recovery in open-ended web/code tasks.

#### Comprehensive Surveys
- **[A Survey on Large Language Model based Autonomous Agents](https://arxiv.org/abs/2308.11432)** (Wang et al., 2023)
  - Comprehensive breakdown of agent construction, planning mechanisms, memory structures, and cooperation vs. adversarial dynamics.
- **[The Rise and Potential of Large Language Model Based Agents: A Survey](https://arxiv.org/abs/2309.07864)** (Xi et al., 2023)
  - Systematically categorizes multi-agent interaction topologies into cooperative, competitive, and human-agent collaborative frameworks.