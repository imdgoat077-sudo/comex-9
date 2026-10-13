Here are the foundational and most impactful research papers on multi-agent orchestration and coordination:

#### 1. Core Frameworks & Architectures
- **[AgentVerse: Facilitating Multi-Agent Collaboration and Exploring Emergent Behaviors](https://arxiv.org/abs/2308.10848)**
  * **Authors:** Weize Chen, Yusheng Su, Jingwei Zuo, et al.
  * **Key contribution:** Formalizes group dynamics for LLM agents across four orchestration stages: Expert Recruitment, Collaborative Decision-Making, Action Execution, and Evaluation/Refinement. Supports both autonomous and guided collaboration structures.
- **[AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155)**
  * **Authors:** Qingyun Wu, Gagan Bansal, Jieyu Zhang, et al. (Microsoft Research)
  * **Key contribution:** Introduces conversational programming where multi-agent orchestration is structured as customizable, conversable agents using event-driven control flows, human-in-the-loop triggers, and dynamic routing.
- **[MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352)**
  * **Authors:** Sirui Hong, Mingchen Zhuge, Jonathan Chen, et al.
  * **Key contribution:** Introduces Standard Operating Procedures (SOPs) into multi-agent systems, enforcing structured communication diagrams and role-playing architectures to eliminate orchestration drift and cascading hallucination.
- **[ChatDev: Communicative Agents for Software Development](https://arxiv.org/abs/2307.07924)**
  * **Authors:** Chen Qian, Xin Cong, Wei Liu, et al.
  * **Key contribution:** Employs the waterfall model (Designing, Coding, Testing, Documenting) orchestrated via alternating peer review and sequential conversational phases.

#### 2. Communication Topology & Graph-Based Orchestration
- **[Talk Structurally, Act Hierarchically: A Collaborative Framework for LLM Multi-Agent Systems](https://arxiv.org/abs/2502.11098)**
  * **Authors:** Zhao Wang, Sota Moriyama, Wei-Yao Wang, et al.
  * **Key contribution:** Introduces *TalkHier*, organizing agent interaction into hierarchical topologies to avoid flat communication overhead and semantic distortion across complex subtask trees.
- **[DHCG: Dynamic Construction of Hierarchical Collaboration Graphs for LLM-Based Multi-Agent Reasoning](https://arxiv.org/abs/2610.07835)**
  * **Authors:** Jie Ren, Jiakang Yuan, Chenyu Huang, et al.
  * **Key contribution:** Dynamically constructs Directed Acyclic Graphs (DAGs) representing agent-task dependencies at runtime instead of relying on fixed communication paths.
- **[WorkflowOps: Learning Agent Collaboration Priors for Multi-Agent Workflow Orchestration](https://arxiv.org/abs/2610.07860)**
  * **Authors:** Qi Cheng, Shengyu Chen, Wei Cheng, et al.
  * **Key contribution:** Formulates workflow composition as a learned graph optimization problem, selecting agent interaction routes based on task-specific competency profiles.

#### 3. Efficiency, Routing & Latency Optimization
- **[SquidAgent: Parallelize Wisely, Coordinate Efficiently](https://arxiv.org/abs/2610.08647)** *(NeurIPS 2026)*
  * **Authors:** Yexiong Lin, Shanshan Ye, Yu Yao, et al.
  * **Key contribution:** Addresses the latency bottleneck of sequential multi-agent execution by dynamically identifying parallelizable subproblems versus sequential dependencies.
- **[Token-Efficient Multi-Agent Collaboration via System One-Guided Computational Division of Labor](https://arxiv.org/abs/2610.08155)**
  * **Authors:** Zihan Zhou, Xinzhe Hu, Hanxu Yang, et al.
  * **Key contribution:** Decouples coordination tasks (message routing, scheduling, role assignment) from heavy reasoning agents using lightweight controller routing, slashing token footprints.

#### 4. Diagnostic & Failure Analysis
- **[Know the Shape, Find the Fault: Topology-Conditioned Diagnosis of Multi-Agent LLM Failures](https://arxiv.org/abs/2610.10126)**
  * **Authors:** Xinwen Liu, Zhuocheng Pan, Isabella Zhu, et al.
  * **Key contribution:** Systematically categorizes failure modes (deadlocks, echo chambers, cascading errors) based on the structural topology (chain, star, tree, mesh) of multi-agent orchestration.