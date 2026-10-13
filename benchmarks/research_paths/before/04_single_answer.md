Key research papers on multi-agent orchestration, categorised by foundational frameworks, communication/collaboration dynamics, and architectural surveys:

---

#### 1. Foundational Systems & Frameworks
- **[AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155)** (Wu et al., 2023)
  - **Contribution:** Formulates multi-agent orchestration through conversable agents, integrating automated LLM personas, code execution, and human-in-the-loop controls.
  - **Relevance:** The primary standard for conversational multi-agent orchestration.
- **[MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352)** (Hong et al., ICLR 2024)
  - **Contribution:** Embeds Standardized Operating Procedures (SOPs) into multi-agent workflows to assign distinct software development roles (architect, engineer, tester) and enforce structured communication artifacts.
  - **Relevance:** Foundational blueprint for deterministic, schema-constrained multi-agent orchestration.
- **[AgentVerse: Facilitating Multi-Agent Collaboration and Exploring Emergent Behaviors](https://proceedings.iclr.cc/paper_files/paper/2024/hash/578e65cdee35d00c708d4c64bce32971-Abstract-Conference.html)** (Chen et al., ICLR 2024)
  - **Contribution:** Orchestrates multi-agent teams across explicit stages: recruitment, collaborative decision-making, independent execution, and evaluation.
  - **Relevance:** Explores emergent problem-solving behaviors and dynamic team composition.

---

#### 2. Dynamic, Graph-Based & Adaptive Orchestration
- **[Multi-Agent Collaboration via Evolving Orchestration](https://proceedings.neurips.cc/paper_files/paper/2025/hash/f1320d2e2842169c6fc89dcbd80e94d0-Abstract-Conference.html)** (Dang et al., NeurIPS 2025/2026)
  - **Contribution:** Proposes dynamic centralized orchestration where communication topology and task delegation evolve based on intermediate execution outcomes rather than fixed prompts.
  - **Relevance:** Addresses rigid topologies in static agent graphs.
- **[SquidAgent: Parallelize Wisely, Coordinate Efficiently](https://arxiv.org/abs/2610.08647)** (Lin et al., NeurIPS 2026)
  - **Contribution:** Introduces optimal parallelization techniques for sub-agent coordination to reduce end-to-end latency without degradation from inter-agent noise.
  - **Relevance:** Optimizes parallel orchestration efficiency and latency trade-offs.
- **[WorkflowOps: Learning Agent Collaboration Priors for Multi-Agent Workflow Orchestration](https://arxiv.org/abs/2610.07860)** (Cheng et al., 2026)
  - **Contribution:** Focuses on learning latent graph collaboration structures and routing policies directly from previous interaction traces.
  - **Relevance:** Bridges workflow automation with adaptive policy learning.

---

#### 3. Communication Topologies & Comprehensive Surveys
- **[LLM-Based Multi-Agent Orchestration: A Survey of Frameworks, Communication Protocols, and Emerging Patterns](https://www.preprints.org/manuscript/202604.2147)** (Zhu et al., 2026)
  - **Contribution:** Taxonomizes coordination paradigms (hierarchical, peer-to-peer, debate, shared memory boards) and surveys modern protocol implementations across frameworks.
  - **Relevance:** Comprehensive reference for system topologies and design patterns.
- **[Know the Shape, Find the Fault: Topology-Conditioned Diagnosis of Multi-Agent LLM Failures](https://arxiv.org/abs/2610.10126)** (Liu et al., 2026)
  - **Contribution:** Investigates failure patterns (cascading hallucinations, deadlock, groupthink) conditional on orchestration graph topology.
  - **Relevance:** Essential for debugging, observability, and robust multi-agent architecture.