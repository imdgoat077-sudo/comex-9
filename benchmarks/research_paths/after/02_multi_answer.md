Top research papers on multi-agent orchestration, grouped by architecture frameworks, surveys/taxonomies, and evaluation benchmarks.

### Foundational Architecture Frameworks

- [AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155) (2023)
  - Authors: Qingyun Wu, Gagan Bansal, Jieyu Zhang, et al.
  - Citations: 2,873 (Semantic Scholar)
  - Orchestration mechanism: Conversable agent abstraction supporting flexible topologies, dynamic LLM-driven speaker selection, static sequential pipelines, nested chats, and human-in-the-loop control.
- [MetaGPT: Meta Programming for Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352) (ICLR 2024 / 2023)
  - Authors: Sirui Hong, Xiawu Zheng, Jonathan Chen, et al.
  - Citations: 2,595 (Semantic Scholar)
  - Orchestration mechanism: Standard operating procedures (SOPs) encoded into assembly-line workflows. Uses structured artifact outputs (PRDs, system designs) and an asynchronous shared message pool with publish-subscribe routing to reduce communication noise.
- [CAMEL: Communicative Agents for "Mind" Exploration of Large Language Model Society](https://arxiv.org/abs/2303.17760) (NeurIPS 2023)
  - Authors: Guohao Li, Hasan Abed Al Kader Hammoud, Hani Itani, Dmitrii Khizbullin, Bernard Ghanem
  - Citations: 1,998 (Semantic Scholar)
  - Orchestration mechanism: Role-playing cooperative framework using inception prompting for autonomous task alignment and execution between paired communicative agents.
- [ChatDev: Communicative Agents for Software Development](https://arxiv.org/abs/2307.07924) (ACL 2024 / 2023)
  - Authors: Cheng Qian, Wei Liu, Hongzhi Gao, et al.
  - Citations: 1,309 (Semantic Scholar)
  - Orchestration mechanism: Waterfall-model phase architecture (Design, Coding, Testing, Documenting) driven by communicative deconstruction into dual-agent chat chains and reflection loops.

### Surveys and Taxonomies

- [A Survey of Agentic Reasoning for Large Language Models: Towards Recursively Self-Improving and Collective Agents](https://arxiv.org/abs/2601.12538) (TMLR / 2026)
  - Authors: Tianxin Wei, Ting-Wei Li, Zhining Liu, et al.
  - Focus: Categorizes reasoning mechanisms across single-agent inference, collective architectures, recursive self-improvement, and multi-agent coordination topologies.
- [Multi-Agent Debate Strategies: Survey, Taxonomy, and Challenges](https://arxiv.org/abs/2607.26212) (ACM Computing Surveys under review / 2026)
  - Authors: Quim Motger, Marc Oriol, Jordi Marco, Xavier Franch
  - Focus: Taxonomizes multi-agent debate (MAD) protocols, critique-consensus dynamics, and communication graph structures.
- [A Survey on Agent Workflow -- Status and Future](https://arxiv.org/abs/2508.01186) (IEEE ICAIBD 2025)
  - Authors: Chaojia Yu, Zihan Cheng, Hanwen Cui, et al.
  - Focus: Analyzes autonomous agent workflow topologies, execution graphs, and dynamic interaction pipelines.
- [From Standalone LLMs to Integrated Intelligence: A Survey of Compound AI Systems](https://arxiv.org/abs/2506.04565) (2025)
  - Authors: Jiayi Chen, Junyi Ye, Guiling Wang
  - Focus: Taxonomizes Compound AI Systems (CAIS), covering planning orchestrators, tool retrievers, and multi-agent integration layers.

### Benchmarks, Coordination Overhead, and Failure Modes

- [Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/abs/2503.13657) (NeurIPS / 2025)
  - Authors: Mert Cemri, Melissa Z. Pan, Shuyi Yang, et al.
  - Focus: Introduces the Multi-Agent System Failure Taxonomy (MAST) and MAST-Data (1,600+ traces over 7 frameworks). Details 14 failure modes across system design flaws, inter-agent misalignment, and task verification collapse.
- [Silo-Bench: A Scalable Environment for Evaluating Distributed Coordination in Multi-Agent LLM Systems](https://arxiv.org/abs/2603.01045) (ACL 2026)
  - Authors: Yuzhe Zhang, Feiran Liu, Yi Shan, et al.
  - Focus: Tests distributed coordination across 30 algorithmic tasks and 54 system setups. Identifies the "Communication-Reasoning Gap" where coordination overhead eliminates parallel scaling benefits during distributed state synthesis.
- [DPBench: Structural Determinants of Multi-Agent LLM Coordination Under Simultaneous Resource Contention](https://arxiv.org/abs/2602.13255) (2026)
  - Authors: Najmul Hasan, Prashanth Busireddygari
  - Focus: Adapts the Dining Philosophers problem to test action protocols, communication graphs, deadlock, and starvation during concurrent resource access.
- [LLM-Coordination: Evaluating and Analyzing Multi-agent Coordination Abilities in Large Language Models](https://arxiv.org/abs/2310.03903) (NAACL / 2023)
  - Authors: S. Agashe, Yue Fan, Anthony Reyna, Xin Eric Wang
  - Focus: Evaluates communication efficiency and coordination failure in cooperative, conflict-free multi-agent games.

### Missing and Uncertain Information

- Domain-specific orchestration frameworks (e.g., finance, healthcare, legal, robotics) were excluded during research to isolate general-purpose architectures.
- Survey paper research hit query action limits before cross-checking full taxonomy sub-sections on Semantic Scholar.
- Benchmark papers were analyzed via abstracts, metadata, and methodology summaries; raw dataset tables and execution traces were not individually verified.