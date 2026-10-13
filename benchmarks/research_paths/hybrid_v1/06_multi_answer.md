Selected research papers on multi-agent orchestration, grouped by taxonomy, system architecture, and evaluation benchmarks:

### Surveys and Taxonomies
- [Large Language Model Based Multi-agents: A Survey of Progress and Challenges](https://doi.org/10.24963/ijcai.2024/890) (IJCAI 2024)
  - Authors: Taicheng Guo, Xiuying Chen, Yaqi Wang, Ruidi Chang, Shichao Pei, et al.
  - Focus: Taxonomies of LLM multi-agent systems covering agent profiling, communication architectures, collaboration mechanisms, and environment simulation.
- [A survey on large language model based autonomous agents](https://doi.org/10.1007/s11704-024-40231-1) (Frontiers of Computer Science 2024)
  - Authors: Lei Wang, Chen Ma, Xueyang Feng, Zeyu Zhang, Hao Yang, et al.
  - Focus: Agent composition (architecture, memory, planning, tools), multi-agent coordination environments, cooperative/competitive dynamics, and collective intelligence patterns (1,807 citations).

### System Designs and Frameworks
- [ChatDev 2.0: A No-Code Multi-Agent Platform for Developing Everything](https://arxiv.org/abs/2609.00714) (EMNLP Demo Track 2026)
  - Authors: Yufan Dang, Shu Yao, Bowen Lai, Chenting Xu, Ruijie Shi, Wai-Shing Leung, Huatao Li, Chen Qian, Zhiyuan Liu.
  - Focus: Visual no-code interaction workflow orchestration engine (DevAll) to build, execute, and inspect heterogeneous multi-agent systems.
- [Nexus Agent: Autonomous Multi-Agent Orchestration Framework and Local GraphRAG Architecture](https://doi.org/10.5281/zenodo.22118830) (Zenodo 2026)
  - Author: Rudra Sarker.
  - Focus: Autonomous multi-agent coordination architecture integrated with local GraphRAG retrieval pipelines.

### Benchmarks, Evaluation, and Failure Analysis
- [PerspectiveGap: A Benchmark for Multi-Agent Orchestration Prompting](http://arxiv.org/abs/2606.08878v2) (arXiv 2026)
  - Authors: Youran Sun, Xingyu Ren, Kejia Zhang, Xinpeng Liu, Jiaxuan Guo.
  - Focus: Evaluates LLMs on composing orchestration prompts and routing information across 10 multi-agent topologies (110 scenarios). Highlights failure modes such as information leakage across sub-agents and low combined pass rates (17.2%).
- [Towards Effective GenAI Multi-Agent Collaboration: Design and Evaluation for Enterprise Applications](http://arxiv.org/abs/2412.05449v1) (arXiv 2024)
  - Authors: Raphael Shu, Nilaksh Das, Michelle Yuan, Monica Sunkara, Yi Zhang.
  - Focus: Enterprise domain benchmark comparing coordination mode (parallel communication, payload referencing) versus message routing mode; analyzes orchestration latency, failure mitigation, and payload referencing efficiency.
- [EPOB: End-to-End Project Orchestration Benchmark - Evaluating Multi-Agent AI Frameworks](https://doi.org/10.5281/zenodo.20349945) (Zenodo 2026)
  - Author: Nathan Scott.
  - Focus: Evaluates framework reliability, task decomposition, and coordination in end-to-end multi-agent execution.
- [COLLATOR: Compositional Multi-Agent Orchestration with Counterfactual Reinforcement Learning](http://arxiv.org/abs/2605.14483v2) (arXiv 2026)
  - Authors: Unlisted in retrieved feed record.
  - Focus: Identifies structural orchestration failure modes (sequential role design, capacity assignment, dependency failure) caused by coarse execution feedback; evaluates accuracy-token trade-offs using localized credit signals across six reasoning and coding benchmarks.

### Missing and Uncertain Information
- **Foundational frameworks missing:** Primary landing papers for original releases (such as 2023 MetaGPT or original 2023 AutoGen) were omitted due to browsing limits.
- **Incomplete metadata:** Authors for `COLLATOR` (arXiv 2605.14483v2) were missing from the retrieved feed record. Deep architectural details for `Nexus Agent` could not be retrieved beyond repository metadata.
- **Incomplete failure mode survey:** The final query on multi-agent failure analysis (`export.arxiv.org/api/query?search_query=...failure+mode...`) was reached but terminated before extracting text, leaving further failure taxonomy papers unparsed.