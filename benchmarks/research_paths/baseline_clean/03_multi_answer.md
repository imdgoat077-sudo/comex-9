Key research papers on multi-agent orchestration, categorized by foundational frameworks, architectural surveys, and evaluation/failure benchmarks:

### Foundational Orchestration Frameworks
- [MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352) (Hong et al., 2023)
  - **Contribution:** Encodes Standard Operating Procedures (SOPs) into prompt sequences. Uses an assembly-line paradigm where agents with specialized roles verify intermediate outputs to reduce logic inconsistencies and cascading errors in software workflows.
- [AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155) (Wu et al., 2023)
  - **Contribution:** Introduces conversable, customizable agents supporting human-in-the-loop workflows, tool usage, and programmable multi-agent interaction patterns.

### Surveys and Architectural Taxonomies
- [The Five Ws of Multi-Agent Communication: Who Talks to Whom, When, What, and Why -- A Survey from MARL to Emergent Language and LLMs](https://arxiv.org/abs/2602.11583) (Chen et al., 2026; *TMLR*)
  - **Contribution:** Classifies coordination via the "5W" communication taxonomy: topology/routing (Who), scheduling/synchronization (When), message content/modality (What), and collaboration objectives (Why).
- [Beyond Self-Talk: A Communication-Centric Survey of LLM-Based Multi-Agent Systems](https://arxiv.org/abs/2502.14321) (Yan et al., 2025; *Frontiers of Computer Science*)
  - **Contribution:** Reviews communication paradigms, information routing mechanisms, and coordination protocols structuring agent interactions beyond single-agent prompting.
- [Multi-Agent Debate Strategies: Survey, Taxonomy, and Challenges](https://arxiv.org/abs/2607.26212) (Motger et al., 2026)
  - **Contribution:** Defines a taxonomy for Multi-Agent Debate (MAD) architectures, covering critique protocols, consensus formation, and convergence orchestration.
- [Beyond Individual Intelligence: Surveying Collaboration, Failure Attribution, and Self-Evolution in LLM-based Multi-Agent Systems](https://arxiv.org/abs/2605.14892) (Qi et al., 2026)
  - **Contribution:** Categorizes structured collaboration topologies, role assignments, cross-agent failure propagation, and self-evolution mechanisms.
- [Large Language Models in the Loop: A Stability- and Network-Aware Survey in Networked Control, Cyber-Physical, and Multi-Agent Systems](https://arxiv.org/abs/2609.16599) (Du & Chan, 2026)
  - **Contribution:** Analyzes delay synchronization, feedback loops, and stability constraints when LLMs serve as high-level decision orchestrators in networked agent systems.

### Benchmarks, Coordination Routing, and Failure Modes
- [Error-Propagation Modeling for Failure Attribution in LLM-Based Multi-Agent Systems](https://arxiv.org/abs/2610.11600) (Liao et al., 2026)
  - **Contribution:** Introduces the EMFA model on the *Who&When* benchmark. Evaluates cascading propagation errors and interaction loops, boosting step-level failure attribution accuracy by 3.45 percentage points (Hand-Crafted) and 4.40 percentage points (Algorithm-Generated).
- [MAGMA-Bench: Evaluating Long-Horizon Embodied Agents under Dynamic Tasks and Execution Failures](https://arxiv.org/abs/2610.13534) (Bernat et al., 2026)
  - **Contribution:** Evaluates heterogeneous multi-agent coordination, long-horizon decision-making, and failure recovery under dynamic task execution.
- [Competence-Aware Orchestration for LLM-Based Multi-Agent Systems](https://arxiv.org/abs/2610.13144) (Wang et al., 2026)
  - **Contribution:** Examines dynamic agent capability assessment and task routing mechanisms to prevent suboptimal delegation and execution breakdowns.

### Missing and Uncertain Coverage
- **External Databases:** Semantic Scholar, Google Scholar, and Papers with Code were not queried due to search action limits; all retrieved items are arXiv preprints and associated journal publications.
- **Specific Frameworks:** Landmark frameworks such as ChatDev and CAMEL were not retrieved prior to reaching action limits.
- **Incomplete Metadata:** Metadata for arXiv:2402.01680 was not extracted. Detailed quantitative baselines and full benchmark specifications for *MAGMA-Bench* and *Competence-Aware Orchestration* could not be inspected in depth from their full PDF texts.