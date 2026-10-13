Key research papers on multi-agent orchestration categorized by mechanism:

---

#### 1. Foundational Architecture & Conversational Orchestration

- **AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation**
  - **Authors:** Qingyun Wu et al. (Microsoft Research, 2023)
  - **Paper:** [arXiv:2308.08155](https://arxiv.org/abs/2308.08155)
  - **Core Mechanism:** Introduces conversable agents capable of blending LLMs, human feedback, and tool calls. Orchestration is framed as conversation programming (nested chats, group chat managers, dynamic speaker selection).
  - **Significance:** Standardized conversational orchestration primitives across industry and academia.

- **CAMEL: Communicative Agents for "Mind" Exploration of Large Language Model Society**
  - **Authors:** Guohao Li et al. (KAUST, 2023)
  - **Paper:** [arXiv:2303.17760](https://arxiv.org/abs/2303.17760)
  - **Core Mechanism:** Introduces *inception prompting* to orchestrate cooperative role-playing between autonomous agents (e.g., user-agent and assistant-agent) while preventing conversational loops and hallucination cascades.
  - **Significance:** Pioneered autonomous agent-to-agent communication without constant human steering.

---

#### 2. Workflow, SOP, and Structured Role Orchestration

- **MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework**
  - **Authors:** Sirui Hong et al. (DeepWisdom, 2023)
  - **Paper:** [arXiv:2308.00352](https://arxiv.org/abs/2308.00352)
  - **Core Mechanism:** Encodes Standard Operating Procedures (SOPs) into agent workflows. Uses structured artifact generation (PRDs, design docs, API specs) and a shared publish-subscribe message broker to orchestrate diverse specialized roles (Product Manager, Architect, Engineer).
  - **Significance:** Solved communication noise in open dialogue by enforcing structured, phase-gated execution.

- **Communicative Agents for Software Development (ChatDev)**
  - **Authors:** Chen Qian et al. (Tsinghua University, 2023)
  - **Paper:** [arXiv:2307.07924](https://arxiv.org/abs/2307.07924)
  - **Core Mechanism:** Orchestrates multi-agent development through the classic Waterfall model broken into atomic sub-tasks (Designing, Coding, Testing, Documenting) driven by paired-agent peer review.
  - **Significance:** Demonstrated state-machine-driven multi-agent orchestration for multi-file code synthesis.

---

#### 3. Dynamic Topology, Graph-Based & Adaptive Orchestration

- **Dynamic LLM-Agent Network: An LLM-Agent Collaboration Framework with Agent Team Optimization (DyLAN)**
  - **Authors:** Chenghao Liu et al. (2023)
  - **Paper:** [arXiv:2310.02170](https://arxiv.org/abs/2310.02170)
  - **Core Mechanism:** Represents multi-agent interactions as dynamic feedforward/bipartite layers. Evaluates each agent’s contribution score dynamically and prunes underperforming agents per inference round.
  - **Significance:** Transitioned orchestration from static hardcoded topologies to dynamic, task-adaptive agent graphs.

- **AgentVerse: Facilitating Multi-Agent Collaboration and Exploring Emergent Behaviors**
  - **Authors:** Weize Chen et al. (Tsinghua University, 2023)
  - **Paper:** [arXiv:2308.10848](https://arxiv.org/abs/2308.10848)
  - **Core Mechanism:** Implements a four-phase lifecycle orchestration loop: Recruitment (dynamic team formation), Collaborative Decision Making, Execution, and Evaluation/Feedback.
  - **Significance:** Systematized autonomous dynamic team composition and iterative group consensus protocols.

- **WorkflowOps: Learning Agent Collaboration Priors for Multi-Agent Workflow Orchestration**
  - **Authors:** Qi Cheng et al. (NEC Labs, 2024)
  - **Paper:** [arXiv:2410.07860](https://arxiv.org/abs/2410.07860)
  - **Core Mechanism:** Learns prior structural dependencies across heterogeneous tasks to dynamically select whether agent workflows should be serial, concurrent, or hierarchical.
  - **Significance:** Addresses token efficiency and latency bottlenecks caused by naive exhaustive multi-agent chains.

---

#### 4. Theoretical Foundations & Comprehensive Surveys

- **Large Language Model-Based Multi-Agent Systems: A Survey**
  - **Authors:** Taicheng Guo et al. (2024)
  - **Paper:** [arXiv:2402.01680](https://arxiv.org/abs/2402.01680)
  - **Covers:** Systematic taxonomy of multi-agent communication topologies (centralized, decentralized, hierarchical), orchestration protocols, memory mechanisms, and evaluation benchmarks.

- **A Survey on Large Language Model based Autonomous Agents**
  - **Authors:** Lei Wang et al. (2023)
  - **Paper:** [arXiv:2308.11432](https://arxiv.org/abs/2308.11432)
  - **Covers:** Architecture of agent core modules (Profiling, Memory, Planning, Action) and how multi-agent interactions emerge across competitive and cooperative environments.