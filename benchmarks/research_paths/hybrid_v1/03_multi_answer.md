Key research papers on multi-agent orchestration, categorized by system frameworks, taxonomies, and safety/verification analysis:

### Foundational Systems and Frameworks

- [AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155) (2023)
  - **Authors:** Qingyun Wu, Gagan Bansal, Jieyu Zhang, Yiran Wu, Beibin Li, Erkang Zhu, Li Jiang, Xiaoyun Zhang, Shaokun Zhang, Jiale Liu, Ahmed Hassan Awadallah, Ryen W White, Doug Burger, Chi Wang
  - **Architecture:** Conversable multi-agent conversation framework supporting automated chat and human-in-the-loop workflows across flexible interaction patterns.
  - **Focus:** Integrates LLMs, human inputs, and tools into customizable, conversable agents; enables defining multi-agent choreographies via natural language and programmatic conversation control.

- [MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352) (2023)
  - **Authors:** Sirui Hong, Mingchen Zhuge, Jiaqi Chen, Xiawu Zheng, Yuheng Cheng, Ceyao Zhang, Jinlin Wang, Zili Wang, Steven Ka Shing Yau, Zijuan Lin, Liyang Zhou, Chenyu Ran, Lingfeng Xiao, Chenglin Wu, Jürgen Schmidhuber
  - **Architecture:** Standardized Operating Procedures (SOPs) encoded into prompt sequences, structured communication interfaces, and role-based division of labor.
  - **Focus:** Resolves cascading hallucinations and coordination failures in complex multi-agent workflows through structured outputs and publish-subscribe coordination modeled on software engineering lifecycles.

- [ChatDev: Communicative Agents for Software Development](https://arxiv.org/abs/2307.07924) (2023)
  - **Authors:** Chen Qian, Wei Liu, Hongzhang Liu, Nuo Chen, Yufan Dang, Jiahao Li, Cheng Yang, Weize Chen, Yusheng Su, Xin Cong, Juyuan Xu, Dahai Li, Zhiyuan Liu, Maosong Sun
  - **Architecture:** Sequential multi-phase waterfall model (design, coding, testing, documenting) mediated through bilateral communicative chat chains between specialized agent roles.
  - **Focus:** Demonstrates task-oriented orchestration by breaking down software engineering tasks into multi-agent subtasks via structured dialogue.

- [AgentVerse: Facilitating Multi-Agent Collaboration and Exploring Emergent Behaviors](https://arxiv.org/abs/2308.10848) (2023)
  - **Authors:** Weize Chen, Yusheng Su, Jingwei Zuo, Cheng Yang, Chenfei Yuan, Chi-Min Chan, Heyang Yu, Yaxi Lu, Yi-Hsin Hung, Chen Qian, Yujia Qin, Xin Cong, Ruobing Xie, Zhiyuan Liu, Maosong Sun, Jie Zhou
  - **Architecture:** Dynamic group problem-solving cycles featuring expert recruitment, collaborative decision-making, action execution, and evaluation.
  - **Focus:** Modular runtime environment enabling dynamic role assignment, multi-turn iterative deliberation, and orchestration of agent assemblies to study emergent collaborative behavior.

---

### Architectural Surveys and Taxonomies

- [LLM-Based Multi-Agent Orchestration: A Survey of Frameworks, Communication Protocols, and Emerging Patterns](https://doi.org/10.3390/fi18060326) (Future Internet, advance index date 2026)
  - **Authors:** Yiwen Zhu, Lihe Liu, Jiaqian Yu, Di Zhang
  - **Focus:** Systematic review covering architectural frameworks, inter-agent communication protocols, and emerging orchestration patterns for LLM-based multi-agent coordination.

---

### Verification, Safety, and Failure Modes

- [Orchestration and Verification of Agentic AI Systems: A Survey of Multi-Agent Collaboration and Safety](https://doi.org/59324/ejaset.2026.4(2).16) (2026)
  - **Authors:** Isteak Ahmed Rafe, Md Rasel Dewan, Md Khairul Islam
  - **Focus:** Survey of multi-agent collaboration mechanisms, verification strategies, coordination failure modes, and safety criteria in autonomous orchestration systems.

---

### Limitations and Missing Data
- **Anti-bot blocking:** Google Scholar searches failed due to automated CAPTCHAs, preventing live extraction of citation rankings.
- **Data truncation:** OpenAlex API result limits truncated citation counts and secondary survey papers.
- **Coverage gaps:** Browser action limits prevented the retrieval of primary papers for additional systems (e.g., CAMEL, CrewAI, LangGraph), as well as dedicated experimental evaluation benchmark suites and quantitative performance metrics.