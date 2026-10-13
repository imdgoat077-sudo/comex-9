Research papers on multi-agent orchestration span three primary areas: foundational survey taxonomies, core coordination frameworks, and empirical evaluation benchmarks.

### Surveys and Architectural Taxonomies
- [Large Language Model based Multi-Agents: A Survey of Progress and Challenges](https://arxiv.org/abs/2402.01680) (Guo et al., 2024). Surveys architectural challenges, multi-agent collaboration mechanisms, complex problem-solving workflows, and world simulation environments.
- [Beyond Self-Talk: A Communication-Centric Survey of LLM-Based Multi-Agent Systems](https://arxiv.org/abs/2502.14321) (Yan et al., 2025, *Frontiers of Computer Science*). Classifies message-passing topologies, interaction structures, and inter-agent coordination protocols.
- [Large Language Models in the Loop: A Stability- and Network-Aware Survey in Networked Control, Cyber-Physical, and Multi-Agent Systems](https://arxiv.org/abs/2609.16599) (Du & Chan, 2026). Analyzes multi-agent orchestration under network constraints, stability criteria, and closed-loop control dynamics.

### Core Orchestration Frameworks
- [AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155) (Wu et al., 2023). Introduces conversable agent graphs supporting hierarchical, group chat, and programmable multi-party routing.
- [MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352) (Hong et al., 2023). Implements assembly-line orchestration by encoding Standardized Operating Procedures (SOPs) into structured prompt sequences.
- [CAMEL: Communicative Agents for "Mind" Exploration of Large Language Model Society](https://arxiv.org/abs/2303.17760) (Li et al., 2023). Establishes autonomous peer-to-peer task execution using inception prompting and bilateral role-play coordination.

### Benchmarks, Consensus Protocols, and Failure Dynamics
- [SwarmBench: Can Large Language Models Act as Agent Swarm Orchestrators?](https://arxiv.org/abs/2608.30661) (Gao et al., 2026). Evaluates LLMs acting as dynamic orchestrators over agent swarms; highlights execution quality gaps and mitigates failure modes using experience replay (SwarmExp).
- [LLM-Coordination: Evaluating and Analyzing Multi-agent Coordination Abilities in Large Language Models](https://arxiv.org/pdf/2310.03903.pdf) (Agashe et al., 2023). Tests decentralized consensus and coordination dynamics in pure coordination games without central supervisors.
- [Silo-Bench: A Scalable Environment for Evaluating Distributed Coordination in Multi-Agent LLM Systems](https://www.semanticscholar.org/paper/Silo-Bench%3A-A-Scalable-Environment-for-Evaluating-Zhang-Liu/4d94b0a424264ea5ea7fa7df87f3ddbceee35070) (Zhang et al., 2026). Evaluates communication scaling bottlenecks; finds that increasing agent count fails to overcome context limitations.
- [How Much Coordination Gain Is Real? A Paired Noise-Floor Protocol for Multi-Agent LLM Benchmarks](https://arxiv.org/pdf/2606.20695.pdf) (Kaliyev & Maryanskyy, 2026). Evaluates illusory coordination improvements; defines a paired noise-floor audit metric (`pass^k` restricted to trials where coordination logic is actively executed).
- [Benchmarking Open-Ended Multi-Agent Coordination in Language Agents](https://arxiv.org/pdf/2606.08340.pdf) (Tessera et al., 2026). Introduces the Alem environment to quantify bottlenecks in dynamic role assignment, plan execution, and communication load.

### Missing and Uncertain Information
- Google Scholar bot detection blocked citation count retrieval across all papers; relative citation rank cannot be confirmed.
- Action execution limits halted retrieval before collecting paper metadata for ChatDev (`arXiv:2307.07924`) and graph-based workflow engines (such as LangGraph).
- Quantitative ablation tables, token usage breakdowns, and exact latency metrics for benchmarks like SwarmBench were not extracted.