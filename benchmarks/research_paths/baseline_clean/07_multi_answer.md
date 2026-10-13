Research papers on multi-agent orchestration group into foundational execution architectures, comprehensive surveys and taxonomies, and benchmarks addressing coordination failures.

### Foundational Execution Architectures

- [Generative Agents: Interactive Simulacra of Human Behavior](https://www.semanticscholar.org/paper/Generative-Agents%3A-Interactive-Simulacra-of-Human-Park-O'Brien/5278a8eb2ba2429d4029745caf4e661080073c81)
  - **Authors:** Joon Sung Park, Joseph C. O'Brien, Carrie J. Cai, Meredith Ringel Morris, Percy Liang, Michael S. Bernstein (ACM UIST 2023, 5,946+ citations).
  - **Mechanism:** Memory stream architecture with dynamic retrieval (recency, importance, relevance), periodic reflection synthesis, and recursive planning/reaction loops in an interactive sandbox.
  - **Contribution:** Foundational architecture for cognitive execution loops and decentralized multi-agent social coordination.

- [AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://www.semanticscholar.org/paper/AutoGen%3A-Enabling-Next-Gen-LLM-Applications-via-Wu-Bansal/9ea0757c750ab1222a7442d3485a74d1c526b04c)
  - **Authors:** Qingyun Wu, Gagan Bansal, Chi Wang, et al. (arXiv:2308.08155 / Technical Report 2023, 2,873+ citations).
  - **Mechanism:** Conversable agent paradigm supporting programmable multi-agent conversational patterns (two-person chat, sequential chats, group chat manager with dynamic speaker selection), tool usage, and human-in-the-loop integration.
  - **Contribution:** Formalized multi-agent execution as programmable conversation and autonomous turn-taking.

- [MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://www.semanticscholar.org/paper/MetaGPT%3A-Meta-Programming-for-A-Multi-Agent-Hong-Zhuge/792fd55d79d120173e0a944ce6bfe4787239c1d2)
  - **Authors:** Sirui Hong, Mingchen Zhuge, Jonathan Chen, Xiawu Zheng, Cheng-Lin Wu, Jürgen Schmidhuber, et al. (ICLR 2024 / arXiv:2308.00352, 2,595+ citations).
  - **Mechanism:** Standard Operating Procedures (SOPs) encoded via meta-programming into an assembly-line pipeline with publish-subscribe message brokers, shared memory pools, and structured artifacts.
  - **Contribution:** Enforces structured role specialization over free-form chat to reduce cascading hallucinations in collaborative software engineering pipelines.

- [ChatDev: Communicative Agents for Software Development](https://www.semanticscholar.org/paper/ChatDev%3A-Communicative-Agents-for-Software-Qian-Liu/9474b463654fd92a62c103b21f95aed94b087907)
  - **Authors:** Cheng Qian, Wei Liu, Hongzhi Gao, Dangyang Chen, Yufan Dang, Maosong Sun, et al. (ACL 2024 / arXiv:2307.07924, 1,309+ citations).
  - **Mechanism:** Waterfall-model execution (designing, coding, testing, documenting) split into atomic "chat chains" using paired instructor-assistant dialogues with self-reflection.
  - **Contribution:** Baseline framework for decomposing systemic tasks into sequential two-agent communicative workflows.

### Comprehensive Surveys and Taxonomies

- [Large Language Model based Multi-Agents: A Survey of Progress and Challenges](https://arxiv.org/pdf/2402.01680.pdf)
  - **Authors:** Taicheng Guo, Xiu-Ying Chen, Xiangliang Zhang, et al. (IJCAI / arXiv 2024, 1,252 citations).
  - **Scope:** Deconstructs multi-agent systems into environmental domains, agent profiling, communication mechanisms, and skill evolution methods.

- [Exploring Large Language Model‐Based Intelligent Agents: Definitions, Methods, and Prospects](https://doi.org/10.1002/widm.70111)
  - **Authors:** Yu-Heng Cheng, Ceyao Zhang, Xiu-Qiang He, et al. (WIREs Data Mining and Knowledge Discovery 2024, 229 citations).
  - **Scope:** Deconstructs single- and multi-agent systems into planning, memory, profiling, interaction mechanisms, and multi-agent coordination topologies.

- [Beyond Self-Talk: A Communication-Centric Survey of LLM-Based Multi-Agent Systems](https://arxiv.org/pdf/2502.14321.pdf)
  - **Authors:** Bing-Yu Yan, Xiao-Ming Zhang, Chao-Zhuo Li, et al. (arXiv 2025, 90 citations).
  - **Scope:** Focuses on communication-centric orchestration, categorizing system topologies, interaction protocols, and negotiation mechanisms.

- [LLMs Working in Harmony: A Survey on the Technological Aspects of Building Effective LLM-Based Multi Agent Systems](https://arxiv.org/pdf/2504.01963.pdf)
  - **Authors:** R. M. Aratchige, W. M. K. S. Ilmini (arXiv 2025, 16 citations).
  - **Scope:** Categorizes architectural paradigms for scalability, collaboration patterns, and dynamic adaptability.

### Benchmarks, Coordination Failures, and Runtime Monitoring

- [AgentWorld: Benchmarking Long-Horizon Collaboration of Multi-agent LLMs](https://arxiv.org/abs/2609.31590)
  - **Authors:** Raphael Shu, Yusen Zhang, Young Min Cho, et al. (COLM 2026).
  - **Scope:** Benchmarks long-horizon collaboration (3–20 asymmetric agents across 50+ rounds). Introduces Causal Collaboration Effectiveness (CCE) to measure causal dependency of agent actions against task success.
  - **Key Failure Modes:** Role confusion, communication breakdowns, and inability to maintain shared plans.

- [Error-Propagation Modeling for Failure Attribution in LLM-Based Multi-Agent Systems](https://arxiv.org/abs/2610.11600)
  - **Authors:** Jiaqi Liao, Yuanzhao Zhai, Huanxi Liu, et al. (arXiv:2610.11600, 2026).
  - **Scope:** Failure attribution methodology for step- and agent-level root causes on the Who&When benchmark.
  - **Key Failure Modes:** Cascading error propagation across interaction steps and persistent interaction loops where symptom errors mask the decisive root error.

- [ResonAct: Streaming Metrics for Runtime Diagnosis and Self-Healing in Multi-Agent Systems](https://arxiv.org/abs/2609.34701)
  - **Authors:** Tarun Chintada, Neelamadhav Gantayat, Ishaan Romil, et al. (arXiv:2609.34701, 2026).
  - **Scope:** Streaming control-plane framework monitoring task progress, context health, and tool reliability on AppWorld and enterprise workflows to trigger runtime self-healing.
  - **Key Failure Modes:** Tool degradation, context propagation loss, and infinite agent interaction loops.

### Missing and Uncertain Information

- Search sessions reached browser step limits before extracting abstract details for the candidate evaluation paper `DCFA` ([arXiv:2609.04749](https://arxiv.org/abs/2609.04749)) and before running broader arXiv queries on LLM multi-agent surveys.
- Semantic Scholar returned HTTP 400 errors on Boolean searches containing sort parameters (`sort=citation-count`, `sort=is-influential`), preventing systematic citation-ranked filtering for surveys.
- Google Scholar and Papers with Code were not queried due to action limits.
- Benchmark papers reflect preprint status metadata; formal peer-reviewed proceedings are limited to what is listed in their arXiv headers (e.g., COLM 2026 for AgentWorld).