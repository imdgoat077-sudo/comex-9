Here are the landmark and state-of-the-art research papers on multi-agent orchestration, categorized by foundational architectures, dynamic topologies, and system surveys.

---

### 1. Foundational Multi-Agent Orchestration Frameworks

* **AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation**
  * **Authors:** Qingyun Wu, Gagan Bansal, Jieyu Zhang, et al. (Microsoft Research)
  * **Link:** [arXiv:2308.08155](https://arxiv.org/abs/2308.08155)
  * **Core Concept:** Introduces conversational programming where agents act as conversational partners. Orchestration happens through customizable chat managers, state transitions, tool integration, and human-in-the-loop triggers.

* **MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework**
  * **Authors:** Sirui Hong, Mingchen Zhuge, Jonathan Chen, et al. (DeepWisdom)
  * **Link:** [arXiv:2308.00352](https://arxiv.org/abs/2308.00352)
  * **Core Concept:** Applies Standard Operating Procedures (SOPs) from software engineering. Uses structured communication interfaces, document artifacts (PRDs, system designs), and a shared publish-subscribe message broker to prevent conversational drift and hallucinations.

* **CAMEL: Communicative Agents for "Mind" Exploration of Large Language Model Society**
  * **Authors:** Guohao Li, Hasan Abed Al Kader Hammoud, Hani Itani, et al.
  * **Link:** [arXiv:2303.17760](https://arxiv.org/abs/2303.17760)
  * **Core Concept:** Pioneered role-playing multi-agent cooperative problem-solving via inception prompting to ensure autonomous task decomposition without human intervention.

* **ChatDev: Communicative Agents for Software Development**
  * **Authors:** Chen Qian, Xin Cong, Cheng Yang, et al.
  * **Link:** [arXiv:2307.07924](https://arxiv.org/abs/2307.07924)
  * **Core Concept:** Implements a sequential waterfall lifecycle (design, coding, testing, documentation) orchestrated through multi-phase bilateral chat interactions with role-playing verification loops.

---

### 2. Dynamic, Graph-Based & Adaptive Orchestration

* **DyLAN: Dynamic LLM-Agent Network for Effective Multi-Agent Collaboration**
  * **Authors:** Chenghao Liu, Derek Miller, et al.
  * **Link:** [arXiv:2310.02170](https://arxiv.org/abs/2310.02170)
  * **Core Concept:** Replaces static interaction graphs with dynamic network routing. Dynamically ranks agent contributions, pruning unproductive agents and rewiring communication paths at runtime based on task state.

* **AgentVerse: Facilitating Multi-Agent Collaboration and Exploring Emergent Behaviors**
  * **Authors:** Weize Chen, Yusheng Su, Jingwei Zuo, et al. (Tsinghua University)
  * **Link:** [arXiv:2308.10848](https://arxiv.org/abs/2308.10848)
  * **Core Concept:** Deconstructs orchestration into four distinct phases: Expert Recruitment, Collaborative Decision Making, Action Execution, and Evaluation/Refinement. Supports both horizontal and vertical organizational layouts.

* **WorkflowOps: Learning Agent Collaboration Priors for Multi-Agent Workflow Orchestration**
  * **Authors:** Qi Cheng, Shengyu Chen, Wei Cheng, et al.
  * **Link:** [arXiv:2410.07860](https://arxiv.org/abs/2410.07860)
  * **Core Concept:** Focuses on learning agent execution topologies and routing priors directly from workflow data to automate dynamic dependency graphs.

* **SquidAgent: Parallelize Wisely, Coordinate Efficiently**
  * **Authors:** Yexiong Lin, Shanshan Ye, Yu Yao, et al.
  * **Link:** [arXiv:2410.08647](https://arxiv.org/abs/2410.08647)
  * **Core Concept:** Addresses high latency in sequential multi-agent execution by dynamically identifying independent subtasks for safe parallelization while coordinating inter-dependent states.

---

### 3. Surveys & System Taxonomies

* **A Survey on Large Language Model-Based Multi-Agent Systems**
  * **Authors:** Taicheng Guo, Xiuying Chen, Yaqi Wang, et al.
  * **Link:** [arXiv:2402.01680](https://arxiv.org/abs/2402.01680)
  * **Core Concept:** Comprehensive taxonomy covering agent profiling, communication protocols (decentralized vs. centralized, layered, graph-based), coordination mechanisms, and environmental feedback.

* **The Rise and Potential of Large Language Model Based Agents: A Survey**
  * **Authors:** Zhiheng Xi, Wenxiang Chen, Xin Guo, et al. (Fudan University)
  * **Link:** [arXiv:2309.07864](https://arxiv.org/abs/2309.07864)
  * **Core Concept:** Surveys single and multi-agent conceptual architectures, highlighting memory structures, planning paradigms, and multi-agent interaction patterns.

---

### Key Architectural Patterns in Orchestration

- **Centralized / Hierarchical (Hub-and-Spoke):** Single orchestrator agent routes subtasks and aggregates results (e.g., AutoGen GroupChatManager).
- **Assembly / Sequential Pipeline:** Structured step-by-step handoffs using SOPs and schemas (e.g., MetaGPT, ChatDev).
- **Dynamic Directed Acyclic Graphs (DAGs):** Agents determine execution graphs dynamically based on intermediate intermediate task states (e.g., DyLAN, LangGraph concepts).