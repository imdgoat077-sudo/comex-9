Key research papers on multi-agent orchestration, categorized by system architecture, survey, and benchmarking:

### Foundational Execution Architectures

- **[AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155)** (2023)  
  *Authors:* Qingyun Wu, Gagan Bansal, Jieyu Zhang, et al.  
  *Mechanism:* Multi-agent conversation framework using customizable, conversable agents. Orchestrates execution through multi-turn dialogue patterns, tool calling, and human-in-the-loop intervention programmable via natural language and code.
- **[MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352)** (2023) | [Code Repository](https://github.com/geekan/MetaGPT)  
  *Authors:* Sirui Hong, Mingchen Zhuge, Jiaqi Chen, et al.  
  *Mechanism:* Encodes Standard Operating Procedures (SOPs) into prompt sequences. Orchestrates tasks across specialized agent roles using an assembly-line workflow paradigm and structured communication interfaces.
- **[ChatDev: Communicative Agents for Software Development](https://arxiv.org/abs/2307.07924)** (2023) | [Code Repository](https://github.com/OpenBMB/ChatDev)  
  *Authors:* Chen Qian, Wei Liu, Hongzhang Liu, et al.  
  *Mechanism:* Sequential waterfall orchestration executed via peer chats. Uses "chat chains" and communicative dehallucination across design, coding, and testing phases.

### Surveys and Framework Taxonomies

- **[LLM-Based Multi-Agent Orchestration: A Survey of Frameworks, Communication Protocols, and Emerging Patterns](https://doi.org/10.3390/fi18060326)** (2026, *Future Internet*)  
  *Authors:* Yiwen Zhu, Lihe Liu, Jiaqian Yu, Di Zhang  
  *Scope:* Analyzes orchestration framework architectures, inter-agent communication protocols, and multi-agent coordination patterns.

### Benchmarks and Evaluation Frameworks

- **[MASBench: Benchmarking LLM-based Multi-Agent Collaboration under Partial Observability](https://arxiv.org/abs/2610.04672)** (2026)  
  *Authors:* Qizhi Chu, Zekai Yu, Sijie Wen, et al.  
  *Focus:* Benchmarks multi-agent coordination under partially observable settings across Reasoning, Scheduling, and Game tasks. Evaluates three collaboration mechanisms (Protocol, Memory, Routing) using performance score, communication overhead, and cost-effectiveness metrics.
- **[GraphMAS: A Systematic Benchmark of Multi-Agent Coordination for Graph Learning](https://arxiv.org/abs/2609.39777)** (2026)  
  *Authors:* Jiayi Yang, Yifang Chen, Yuanfu Sun, et al.  
  *Focus:* Evaluates seven coordination methods across four interaction paradigms under a unified protocol. Finds richer inter-agent communication does not consistently yield improvements, whereas dynamic specialist selection optimizes the accuracy-efficiency trade-off.
- **[EPOB: End-to-End Project Orchestration Benchmark - Evaluating Multi-Agent AI Frameworks](https://doi.org/10.5281/zenodo.20349945)** (2026)  
  *Authors:* Nathan Scott  
  *Focus:* Evaluates multi-agent frameworks on end-to-end task decomposition, orchestration workflows, and execution efficiency.

---

### Limitations and Missing Coverage

- **Competitive and adversarial orchestration:** Competitive architectures (such as multi-agent debate and game-theoretic setups) were not retrieved.
- **Access limits:** Google Scholar queries were blocked by a bot-detection CAPTCHA.
- **Unverified metadata:** AutoGen's direct source repository was not verified on its abstract page. Full numerical benchmark score tables and deeper sub-taxonomies were not retrieved.