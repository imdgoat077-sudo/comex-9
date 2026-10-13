Here are the foundational and most influential research papers on multi-agent orchestration, categorized by framework architectures, communication topologies, dynamic routing, and surveys.

---

#### 1. Foundational Orchestration Frameworks

* **[AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation Framework](https://arxiv.org/abs/2308.08155)**
  * **Authors:** Qingyun Wu, Chi Wang, et al. (Microsoft Research)
  * **Core Contribution:** Introduces conversable agents as a unified programming abstraction. Supports flexible orchestration topologies: sequential, hierarchical, group-chat manager, and nested execution loops.

* **[MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352)**
  * **Authors:** Sirui Hong, Chenglin Wu, et al. (ICLR 2024)
  * **Core Contribution:** Encodes Standard Operating Procedures (SOPs) into multi-agent workflows. Uses structured communication interfaces (documents, schemas) rather than raw dialogue to prevent context degradation and cascade errors.

* **[ChatDev: Communicative Agents for Software Development](https://arxiv.org/abs/2307.07924)**
  * **Authors:** Chen Qian, Zhiyuan Liu, Maosong Sun, et al. (ACL 2024)
  * **Core Contribution:** Proposes "chat chain" orchestration, decomposing complex software design tasks into sequential phases (designing, coding, testing, documenting) executed by specialized agent pairs with peer review.

---

#### 2. Dynamic Routing & Topology Control

* **[Dynamic LLM-Agent Network (DyLAN): Dynamic LLM-Agent Network for Effective and Efficient Multi-Agent Collaboration](https://arxiv.org/abs/2310.02170)**
  * **Authors:** Zijun Liu, Yichao Du, Rui Wang, et al. (ICLR 2024)
  * **Core Contribution:** Addresses fixed-topology inefficiency. Introduces dynamic agent selection based on contribution scoring (Agent Importance Score), automatically pruning unproductive agents during iterative execution.

* **[More Agents Is All You Need](https://arxiv.org/abs/2402.05120)**
  * **Authors:** Junyou Li, Qin Zhang, Yang Xiao, et al.
  * **Core Contribution:** Analyzes multi-agent scaling laws. Evaluates collaborative ensemble mechanisms, majority voting, and round-robin dialogue against single-agent query scaling.

* **[SquidAgent: Parallelize Wisely, Coordinate Efficiently](https://arxiv.org/abs/2410.08647)**
  * **Authors:** Yexiong Lin, Shanshan Ye, Yu Yao, et al. (NeurIPS 2024)
  * **Core Contribution:** Focuses on orchestrating parallel versus sequential agent task graphs to balance execution latency, token cost, and inter-agent communication overhead.

---

#### 3. Agent Communication & Consensus Paradigms

* **[Improving Factuality and Reasoning in Language Models through Multiagent Debate](https://arxiv.org/abs/2305.14325)**
  * **Authors:** Yilun Du, Shuang Li, Antonio Torralba, Joshua B. Tenenbaum, Igor Mordatch (MIT / Google Brain)
  * **Core Contribution:** Formalizes the multi-agent debate protocol. Orchestrates competing agent perspectives across multiple rounds to reduce hallucinations and improve logical deduction.

* **[Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442)**
  * **Authors:** Joon Sung Park, Joseph C. O'Brien, Percy Liang, Michael S. Bernstein (Stanford / Google)
  * **Core Contribution:** Seminal paper for memory-driven multi-agent simulation. Details orchestration through memory streams, importance scoring, periodic reflection, and recursive retrieval.

---

#### 4. Comprehensive Surveys & Taxonomies

* **[A Survey on LLM-based Multi-Agent Systems: Recent Advances and New Frontiers](https://arxiv.org/abs/2402.01680)**
  * **Authors:** Taicheng Guo, Xiuying Chen, Yaohua Wang, et al.
  * **Core Contribution:** Classifies orchestration mechanisms into cooperative vs. adversarial settings, static vs. dynamic topologies, and centralized vs. decentralized decision engines.

* **[The Five Ws of Multi-Agent Communication: Who Talks to Whom, When, What, and Why](https://arxiv.org/abs/2402.11583)**
  * **Authors:** Jingdi Chen, Carlee Joe-Wong, et al. (TMLR)
  * **Core Contribution:** Systematic taxonomy of communication protocols bridging multi-agent reinforcement learning (MARL) and LLM agent orchestration networks.