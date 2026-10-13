Key research papers on multi-agent orchestration, categorised by foundational systems, theoretical frameworks, and orchestration paradigms:

#### 1. Foundational Architecture & Seminal Frameworks
- **[AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155)** (Wu et al., 2023)
  - Introduces multi-agent conversation programming. Defines customizable, conversable agents that integrate LLMs, human inputs, and tool use to execute multi-step workflows.
- **[MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352)** (Hong et al., ICLR 2024)
  - Implements Standard Operating Procedures (SOPs) into multi-agent orchestration, assigning distinct roles (architect, engineer, tester) to mitigate cascading errors and hallucination loops.
- **[ChatDev: Communicative Agents for Software Development](https://arxiv.org/abs/2307.07924)** (Qian et al., ACL 2024)
  - Demonstrates phased waterfall orchestration (design, coding, testing, documentation) using communicative agent pairs governed by chat chains.

#### 2. Surveys & Taxonomy of Orchestration Mechanisms
- **[Multi-Agent Collaboration Mechanisms: A Survey of LLMs](https://arxiv.org/abs/2501.06322)** (Tran et al., 2025)
  - Comprehensive taxonomy covering interaction topologies (centralized, decentralized, hierarchical), communication protocols, consensus mechanisms, and dynamic role allocation.
- **[A Survey on Large Language Model based Autonomous Agents](https://arxiv.org/abs/2308.11432)** (Wang et al., Frontiers of Computer Science 2024)
  - Systematically analyzes individual agent architectures alongside multi-agent cooperative, competitive, and emergent orchestration dynamics.

#### 3. Dynamic Graphs, Consensus, & Scheduling
- **[AgentNet: Decentralized Evolutionary Coordination for LLM-Based Multi-Agent Systems](https://proceedings.neurips.cc/paper_files/paper/2025/hash/9a379c1b05793d1c42dc832269834515-Abstract-Conference.html)** (Yang et al., NeurIPS)
  - Replaces rigid hardcoded directed acyclic graphs (DAGs) with an evolutionary, decentralized graph topology that adapts agent interactions at runtime.
- **[WorkflowOps: Learning Agent Collaboration Priors for Multi-Agent Workflow Orchestration](https://arxiv.org/abs/2610.07860)** (Cheng et al., arXiv:2610.07860)
  - Formalizes workflow orchestration via learned collaboration priors rather than manual prompt chaining, optimizing execution latency and token overhead.
- **[OSC: Cognitive Orchestration through Dynamic Knowledge Alignment in Multi-Agent LLM Collaboration](https://aclanthology.org/anthology-files/pdf/findings/2025.findings-emnlp.335.pdf)** (Zhang et al., Findings of EMNLP)
  - Focuses on resolving cognitive misalignment and information entropy between heterogeneous specialist models during collaborative execution.

#### 4. Benchmarking Orchestration Efficacy
- **[Beyond the Strongest LLM: Multi-Turn Multi-Agent Orchestration vs. Single LLMs on Benchmarks](https://arxiv.org/abs/2509.23537)** (Tian et al., arXiv:2509.23537)
  - Rigorous evaluation comparing multi-agent orchestration vs. monolithic single-model scaling, identifying exact boundary conditions where multi-agent delegation yields measurable gains over single strong LLMs.