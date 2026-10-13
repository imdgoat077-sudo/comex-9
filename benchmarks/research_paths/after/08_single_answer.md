Multi-agent orchestration research centers on coordination patterns, communication topologies, dynamic role assignment, and cognitive consensus mechanisms.

Key research papers categorized by domain and architecture:

#### 1. Foundational Multi-Agent Frameworks & Topologies
- **MetaGPT: Meta Programming for a Multi-Agent Collaborative Framework**  
  *Authors:* Sirui Hong et al. (ICLR 2024)  
  *Focus:* Encodes human Standard Operating Procedures (SOPs) into structured prompt sequences and intermediate artifacts (PRDs, architecture diagrams, code reviews). Introduces publish-subscribe communication pipelines to eliminate unstructured chat clutter.  
  *Link:* [MetaGPT Paper](https://proceedings.iclr.cc)

- **AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation**  
  *Authors:* Qingyun Wu et al. (Microsoft Research, 2023)  
  *Focus:* Establishes conversational multi-agent orchestration. Formalizes human-in-the-loop delegation, multi-agent group chats, and tool-use integration across specialized LLM personas.  
  *Link:* [arXiv:2308.08155](https://arxiv.org/abs/2308.08155)

- **Communicative Agents for Software Development (ChatDev)**  
  *Authors:* Chen Qian et al. (ACL 2024)  
  *Focus:* Orchestrates agents via sequential phase-based chat chains (designing, coding, testing, documenting) leveraging iterative dual-agent dialogue nodes to resolve ambiguity.  
  *Link:* [arXiv:2307.07924](https://arxiv.org/abs/2307.07924)

#### 2. Advanced Dynamic Orchestration & Scheduling
- **Multi-Agent Collaboration via Evolving Orchestration**  
  *Authors:* Y. Dang, C. Qian, X. Luo, et al. (NeurIPS 2025/2026)  
  *Focus:* Dynamic task graph construction. Formulates agent coordination as a meta-reasoning process where the orchestrator evolves sub-agent teams, routes intermediate context, and adapts interaction graphs dynamically rather than following rigid static SOPs.  
  *Link:* [NeurIPS Proceedings](https://proceedings.neurips.cc/paper_files/paper/2025/hash/f1320d2e2842169c6fc89dcbd80e94d0-Abstract-Conference.html)

- **HALO: Hierarchical Autonomous Logic-Oriented Orchestration for Multi-Agent LLM Systems**  
  *Authors:* Z. Hou, J. Tang, Y. Wang (2025)  
  *Focus:* Hierarchical multi-agent reasoning. Uses a top-level planner agent to construct logic graphs, delegate sub-problems to execution agents, and enforce consistency across distributed outputs.  
  *Link:* [arXiv:2505.13516](https://arxiv.org/abs/2505.13516)

- **Navigating Complexity: Orchestrated Problem Solving with Multi-Agent LLMs**  
  *Authors:* S. Rasal, E. J. Hauer (2024)  
  *Focus:* Algorithmic framework for an Orchestration LLM to decompose high-entropy, cross-domain problems based on sub-domain boundaries, dependency constraints, and agent capability routing.  
  *Link:* [arXiv:2402.16713](https://arxiv.org/abs/2402.16713)

#### 3. Consensus, Alignment & System Architecture
- **OSC: Cognitive Orchestration Through Dynamic Knowledge Alignment in Multi-Agent LLM Collaboration**  
  *Authors:* J. Zhang et al. (EMNLP Findings)  
  *Focus:* Overcomes token churn and hallucination cascades in long agent interactions by synchronizing belief states and aligning cross-agent knowledge representations during collaboration.  
  *Link:* [ACL Anthology](https://aclanthology.org/anthology-files/pdf/findings/2025.findings-emnlp.335.pdf)

- **Beyond the Strongest LLM: Multi-Turn Multi-Agent Orchestration vs. Single LLMs on Benchmarks**  
  *Authors:* A. X. Tian et al. (2025)  
  *Focus:* Empirical performance analysis comparing single frontier models against structured multi-agent coordination protocols on complex reasoning benchmarks.  
  *Link:* [arXiv:2509.23537](https://arxiv.org/abs/2509.23537)

- **LLM-Based Multi-Agent Orchestration: A Survey of Frameworks, Communication Protocols, and Emerging Patterns**  
  *Authors:* Y. Zhu, L. Liu, et al. (2026)  
  *Focus:* Systematic taxonomy of communication topologies (hierarchical, peer-to-peer, blackboard, event-driven), message token cost vs. output quality trade-offs, and state-management protocols across modern multi-agent systems.