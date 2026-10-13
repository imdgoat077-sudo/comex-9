The top research papers on multi-agent orchestration, grouped by surveys, foundational orchestration frameworks, and evaluation benchmarks:

### Comprehensive Surveys and Architectural Taxonomies

*   [Large Language Model based Multi-Agents: A Survey of Progress and Challenges](https://arxiv.org/abs/2402.01680) (IJCAI / arXiv, 2024; 1,252 citations)
    *   **Authors:** Taicheng Guo, Xiu-Ying Chen, et al., Xiangliang Zhang.
    *   **Contribution:** Classifies multi-agent system environments, agent profiling mechanisms, inter-agent communication topologies, and collaborative skill acquisition methods.
*   [A survey on LLM-based multi-agent systems: workflow, infrastructure, and challenges](https://doi.org/10.1007/s44336-024-00009-2) (Vicinagearth / Springer Nature, 2024; 699 citations)
    *   **Authors:** Xinyi Li, Sai Wang, Si-Qi Zeng, Yu Wu, Yi Yang.
    *   **Contribution:** Proposes a five-pillar framework covering profile, perception, self-action, mutual interaction, and evolution to analyze runtime multi-agent execution workflows.
*   [Multi-Agent Collaboration Mechanisms: A Survey of LLMs](https://arxiv.org/abs/2501.06322) (arXiv, 2025; 614 citations)
    *   **Authors:** Khanh-Tung Tran, Dung Dao, Minh-Duong Nguyen, Quoc-Viet Pham, Barry O'Sullivan, Hoang D. Nguyen.
    *   **Contribution:** Formulates an extensible taxonomy for collaborative topologies, collective decision-making, and interaction protocols across LLM agents.
*   [Beyond Self-Talk: A Communication-Centric Survey of LLM-Based Multi-Agent Systems](https://doi.org/10.1007/s11704-026-50857-y) (Frontiers of Computer Science / arXiv, 2025; 90 citations)
    *   **Authors:** Bing-Yu Yan, Xiao-Ming Zhang, et al., Chao-Zhuo Li.
    *   **Contribution:** Evaluates communication-centric system architectures, categorizing system-level versus internal communication protocols, negotiation strategies, and message-routing topologies.

### Foundational Orchestration Frameworks and Runtimes

*   [AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155) (arXiv, 2023)
    *   **Authors:** Qingyun Wu, Gagan Bansal, Jieyu Zhang, Yiran Wu, Beibin Li, Erkang Zhu, et al., Chi Wang.
    *   **Runtime:** Introduces conversable agents operating via customizable execution patterns, supporting dynamic peer-to-peer dialogue, group chat topologies, and human-in-the-loop workflows.
*   [MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352) (arXiv, 2023)
    *   **Authors:** Sirui Hong, Mingchen Zhuge, Jiaqi Chen, Xiawu Zheng, Yuheng Cheng, et al., Jürgen Schmidhuber.
    *   **Runtime:** Encodes Standardized Operating Procedures (SOPs) into structured prompt sequences and message-passing protocols within an assembly-line orchestration model.
*   [WorkflowOps: Learning Agent Collaboration Priors for Multi-Agent Workflow Orchestration](https://arxiv.org/abs/2610.07860) (arXiv, 2026)
    *   **Authors:** Qi Cheng, Shengyu Chen, Wei Cheng, Zhengzhang Chen, Xiaowei Jia, Haoyu Wang, Haifeng Chen.
    *   **Runtime:** Automates workflow execution by learning collaboration priors across agent tasks.
*   [DHCG: Dynamic Construction of Hierarchical Collaboration Graphs for LLM-Based Multi-Agent Reasoning](https://arxiv.org/abs/2610.07835) (arXiv, 2026)
    *   **Authors:** Jie Ren, Jiakang Yuan, Chenyu Huang, Hezeer Ma, Jiayuan Fan, Tao Chen.
    *   **Runtime:** Implements dynamic graph orchestration, constructing hierarchical collaboration graphs dynamically for multi-agent reasoning.

### Evaluation Benchmarks, Failure Modes, and Communication Overhead

*   [DarkForest: Less Talk, Higher Accuracy for Multi-Agent LLMs](https://arxiv.org/abs/2605.25188) (arXiv, 2026)
    *   **Authors:** Yi Li, Song-Tao Wei, Dongming Jiang, Zhi-Chun Guo, Qiannan Li, Bing-Zhe Li.
    *   **Findings:** Measures inter-agent communication overhead; reduces token volume by up to 6.5x while raising accuracy by up to 30.7% by pruning redundant messaging.
*   [MASBench: Benchmarking LLM-based Multi-Agent Collaboration under Partial Observability](https://arxiv.org/abs/2610.04672) (arXiv, 2026)
    *   **Authors:** Qizhi Chu, Zekai Yu, Sijie Wen, Yang Liu, Chen Qian, Cheng Yang, Chuan Shi, Zhiyuan Liu.
    *   **Findings:** Evaluates coordination robustness and task completion failure modes when agents operate without full system observability.
*   [Error-Propagation Modeling for Failure Attribution in LLM-Based Multi-Agent Systems](https://arxiv.org/abs/2610.11600) (arXiv, 2026)
    *   **Authors:** Jiaqi Liao, Yuanzhao Zhai, Huanxi Liu, Xu Zhang, Zheming Zhuang, Dawei Feng, Bo Ding, Huaimin Wang.
    *   **Findings:** Provides mathematical error-propagation models to trace and attribute cascading execution bottlenecks across multi-agent pipelines.
*   [MAGMA-Bench: Evaluating Long-Horizon Embodied Agents under Dynamic Tasks and Execution Failures](https://arxiv.org/abs/2610.13534) (arXiv, 2026)
    *   **Authors:** Loan Bernat, Matthieu Grard, Ariane Herbulot, Florent Lamiraux.
    *   **Findings:** Analyzes dynamic task allocation efficiency, failure recovery rates, and coordination breakdown in heterogeneous long-horizon tasks.

---

### Limitations and Missing Information
*   **Google Scholar Coverage:** Google Scholar blocked automated access via bot detection challenges; citation metrics rely on arXiv and Semantic Scholar records.
*   **Paper Details:** Detailed extraction for ChatDev could not be completed before browser action limits were reached.
*   **Full-Text Benchmark Tables:** Full-text numerical tables for benchmark papers were not downloaded directly; metrics are restricted to abstract disclosures.