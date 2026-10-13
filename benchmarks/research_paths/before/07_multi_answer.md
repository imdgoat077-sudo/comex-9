### Foundational Survey Papers

* **[Multi-agent Collaboration Mechanisms: A Survey of LLMs](https://arxiv.org/abs/2501.06322)**
  * **Authors:** K. T. Tran, D. Dao, M. D. Nguyen, Q. V. Pham, et al.
  * **Focus:** Coordination protocols, communication topologies, and collaborative task allocation.
* **[A Survey on LLM-based Multi-Agent Systems: Workflow, Infrastructure, and Challenges](https://link.springer.com/article/10.1007/s44336-024-00009-2)**
  * **Authors:** X. Li, S. Wang, S. Zeng, Y. Wu, Y. Yang (*Springer*)
  * **Focus:** Infrastructure, orchestrator designs, tool integration, and environment feedback loops.
* **[LLM-Based Multi-Agent Orchestration: A Survey of Frameworks, Communication Protocols, and Emerging Patterns](https://www.preprints.org/manuscript/202604.2147)**
  * **Authors:** Y. Zhu, L. Liu, J. Yu, D. Zhang
  * **Focus:** Centralized vs. decentralized routing, communication protocols, and architectural patterns.
* **[LLM-based Multi-Agent Systems: Frameworks, Evaluation, Open Challenges, and Research Frontiers](https://link.springer.com/chapter/10.1007/978-3-032-15632-7_9)**
  * **Authors:** S. H. Shaikh (*Springer*)
  * **Focus:** Comparative framework evaluations, pipeline reliability, and prompt interfaces.
* **[A Survey on Large Language Model-based Multi-Agent Systems: Paradigms, Applications, and Challenges](https://www.techrxiv.org/doi/pdf/10.36227/techrxiv.177160638.89229642)**
  * **Authors:** M. Zhu et al.
  * **Focus:** Static orchestration pipelines vs. dynamic negotiation frameworks.
* **[Large Language Models in the Loop: A Stability- and Network-Aware Survey in Networked Control, Cyber-Physical, and Multi-Agent Systems](https://arxiv.org/abs/2609.16599)**
  * **Authors:** H. Du, L. Chan
  * **Focus:** Network topologies, communication delay bounds, and control-theoretic stability.

---

### Empirical Frameworks & Benchmarks (NeurIPS, ICLR, ICML)

* **[Multi-Agent Collaboration via Evolving Orchestration](https://arxiv.org/abs/2505.19591)** (NeurIPS)
  * **Framework:** Centralized RL puppeteer dynamically orchestrating specialized LLM agents. Open-source implementation available via [ChatDev/puppeteer](https://github.com/OpenBMB/ChatDev/tree/puppeteer).
* **[Graph-of-Agents: A Graph-based Framework for Multi-Agent LLM Collaboration](https://arxiv.org/abs/2604.17148)** (ICLR)
  * **Framework:** GoA; uses node sampling, dynamic directed relevance edges, and bidirectional message passing. Outperformed Mixture-of-Agents (MoA) on MMLU-Pro, GPQA, and MATH.
* **[A Two-Tier Perspective on Inference-Time Parallelism in Multi-Agent LLM Systems](https://arxiv.org/abs/2608.05791)** (ICML)
  * **Framework:** TIPEX; splits inference into Replica Parallelism and Structural Parallelism. Benchmarked on GAIA.
* **[SquidAgent: Parallelize Wisely, Coordinate Efficiently](https://arxiv.org/abs/2610.08647)** (NeurIPS)
  * **Framework:** Adaptive parallel scheduler resolving multi-agent task dependencies to reduce coordination latency overhead.
* **[CEO Arena: Evaluating Long-Horizon Multi-Agent Decision-Making in Competitive Markets](https://arxiv.org/abs/2609.34821)** (ICLR)
  * **Benchmark:** Empirical evaluation suite for multi-agent competitive orchestration over long horizons.

---

### Findings Comparison

* **Coverage:** Agent 1 gathered broad surveys, taxonomy papers, and control-theoretic angles. Agent 2 gathered peer-reviewed empirical architectures, scheduling methods, and evaluation benchmarks.
* **Consistency:** Both agents agree on the primary technical challenges: dynamic task allocation, communication topology bottlenecks, and coordination overhead. No contradictory claims were found.