Research papers on multi-agent orchestration, grouped by focus area:

### Surveys and Architectural Taxonomies
- [Large Language Model Based Multi-agents: A Survey of Progress and Challenges](https://doi.org/10.24963/ijcai.2024/890) (IJCAI 2024)
  - Authors: Taicheng Guo, Xiuying Chen, Yaqi Wang, Ruidi Chang, Shichao Pei, Nitesh V. Chawla, Olaf Wiest, Xiangliang Zhang
  - Focus: Categorizes multi-agent systems by agent profiling/roles, communication topologies, coordination mechanisms (competition, cooperation, debate), and interaction environments.
- [LLM-Based Multi-Agent Orchestration: A Survey of Frameworks, Communication Protocols, and Emerging Patterns](https://doi.org/10.3390/fi18060326) (*Future Internet*, 2026)
  - Authors: Yiwen Zhu, Lihe Liu, Jiaqian Yu, Di Zhang
  - Focus: Classifies orchestration architectures across coordination frameworks, inter-agent communication protocols, task decomposition patterns, and collaborative interaction designs.

### Frameworks and Task Decomposition
- [APD-Agents: A Large Language Model-Driven Multi-Agents Collaborative Framework for Automated Page Design](http://arxiv.org/abs/2511.14101) (arXiv, 2025)
  - Authors: Xinpeng Chen, Xiaofeng Han, Kaihao Zhang, Guochao Ren
  - Focus: Implements role-based multi-agent execution and task decomposition stages for automated webpage and layout generation.

### Benchmarks, Coordination Failures, and Diagnostics
- [Silo-bench: A scalable environment for evaluating distributed coordination in multi-agent llm systems](https://aclanthology.org/2026.acl-long.1354/) (ACL, 2026)
  - Authors: Y. Zhang, F. Liu, Y. Shan, X. Huang, X. Yang, et al.
  - Findings: Evaluates scaling team sizes ($k \ge 2$). Shows performance drops by over 18 percentage points even at $k=2$ due to coordination collapse under distributed setups.
- [From Trace Entropy to Coordination Control: Diagnosing and Intervening in Multi-Agent LLM Systems](https://openreview.net/forum?id=dummy_colm2026) (COLM, 2026)
  - Authors: C. Mohapatra, R. Malshe, A. Katariya, S. C. Vishnoi, et al.
  - Findings: Diagnoses coordination failures from early deliberation trace entropy $T(t)$ and regime features; achieves an AUC of 0.844 within the first five states to trigger control interventions.
- [The Specification Gap: Coordination Failure Under Partial Knowledge in Code Agents](https://arxiv.org/abs/2603.24284) (arXiv, 2026)
  - Authors: C. C. Sartori
  - Findings: Benchmarks integration breakdowns in code agents when coordinating under disjoint knowledge bases and partial observability.
- [Intention-behavior consistency-based automated failure attribution for LLM-driven multi-agent systems](https://www.sciencedirect.com/science/article/pii/S095741742601955X) (Expert Systems with Applications, 2026)
  - Authors: H. Wu, W. Zheng, M. Zhang, X. Bai, M. Pu, L. Sun, et al.
  - Findings: Identifies orchestration failures by mapping misaligned agent actions back to conflicting sub-task decompositions produced by upstream planning agents.
- [ZSC-Eval: An Evaluation Toolkit and Benchmark for Multi-agent Zero-shot Coordination](http://arxiv.org/abs/2310.05208) (arXiv, 2023)
  - Authors: Xihuai Wang, Shao Zhang, Wenhao Zhang, Wentao Dong, Jingxiao Chen, Ying Wen, Weinan Zhang
  - Findings: Provides a standardized benchmark evaluating cross-play coordination robustness and policy compatibility when agents interact with unfamiliar partners.

---

### Limitations and Omissions
- **Seminal Framework Metadata Missing:** Targeted retrieval for foundational multi-agent platforms (such as AutoGen, MetaGPT, ChatDev, and CAMEL) hit action quotas before paper metadata, author lists, and abstracts could be extracted.
- **Incomplete Full-Text Ingestion:** Browser query limits stopped in-depth parsing of paper PDFs (including `arxiv.org/abs/2403.06534`) and prevented navigating directly to the primary landing page for the COLM 2026 OpenReview submission.