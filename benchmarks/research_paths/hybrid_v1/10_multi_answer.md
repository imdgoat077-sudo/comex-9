The primary research papers on multi-agent orchestration span foundational surveys, seminal coordination frameworks, and evaluation benchmarks.

### Surveys and Taxonomies
* **[A survey on large language model based autonomous agents](https://doi.org/10.1007/s11704-024-40231-1)** (Wang et al., 2024, *Frontiers of Computer Science*)
  * Provides a comprehensive taxonomy of LLM agent architectures, detailing multi-agent environments, communication mechanisms, and cooperative interaction patterns. 1,807 citations.
* **[A Survey of Large Language Models](https://doi.org/10.1007/s11704-026-60308-3)** (Zhao et al., 2024/2026, *Frontiers of Computer Science*)
  * Synthesizes LLM developments including agent planning, tool integration, and multi-agent collaborative task execution frameworks. 1,558 citations.

### Seminal Orchestration Frameworks
* **[AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155)** (Wu et al., 2023)
  * Introduces conversable and customizable agents supporting multiple execution modes (LLMs, tools, humans) orchestrated via programmable conversation patterns in code and natural language.
* **[MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352)** (Hong et al., 2023)
  * Implements an assembly line paradigm encoding Standard Operating Procedures (SOPs) into structured prompts and role-based workflows to prevent cascading agent hallucinations.
* **[ChatDev: Communicative Agents for Software Development](https://arxiv.org/abs/2307.07924)** (Qian et al., 2023)
  * Establishes a phased waterfall orchestration model divided into sequential chat chains with communicative dehallucination across software development lifecycles.
* **[CAMEL: Communicative Agents for "Mind" Exploration of Large Language Model Society](https://arxiv.org/abs/2303.17760)** (Li et al., 2023)
  * Proposes inception prompting to guide autonomous, role-playing cooperation between paired communicative agents without continuous human oversight.

### Benchmarks, Protocols, and Failure Analysis
* **[Seeing the Whole Elephant: A Benchmark for Failure Attribution in LLM-based Multi-Agent Systems](https://doi.org/10.18653/v1/2026.acl-long.912)** (Chen et al., 2026, *ACL*)
  * Formulates protocols and metrics for diagnosing multi-agent breakdowns, tracking error propagation, and isolating root-cause failures across collaborative workflows.
* **[SILO-BENCH: A Scalable Environment for Evaluating Distributed Coordination in Multi-Agent LLM Systems](https://doi.org/10.18653/v1/2026.acl-long.1354)** (Zhang et al., 2026, *ACL*)
  * Evaluates consensus latency, message efficiency, coordination breakdown rates, and distributed multi-agent LLM synchronization bottlenecks.
* **[PerspectiveGap: A Benchmark for Multi-Agent Orchestration Prompting](https://doi.org/10.48550/arxiv.2606.08878)** (Sun et al., 2026)
  * Measures failure modes caused by mismatched context perspectives, role alignment drift, and goal divergence across orchestrator-executor prompts.
* **[PARTNR: A Benchmark for Planning and Reasoning in Embodied Multi-agent Tasks](https://doi.org/10.48550/arxiv.2411.00081)** (Chang et al., 2024)
  * Covers 100,000+ tasks evaluating planning friction, coordination efficiency, belief misalignment, and plan execution stalemates.
* **[EPOB: End-to-End Project Orchestration Benchmark - Evaluating Multi-Agent AI Frameworks](https://doi.org/10.5281/zenodo.20349945)** (Scott, 2026, *Zenodo*)
  * Benchmarks framework reliability during end-to-end task decomposition, dynamic delegation, and recovery from sub-agent pipeline crashes.

### Limitations and Uncovered Areas
* Browser limits truncated OpenAlex API queries before extracting pure-taxonomy preprints (e.g., Guo et al., *Large Language Model based Multi-Agents: A Survey*).
* Full-text PDF execution traces were not retrieved, leaving fine-grained per-metric ablation values unextracted.
* Google Scholar query attempts returned empty pages, restricting framework identification to direct arXiv and OpenAlex records.