# Phase 12F Benchmark Report (Gating Experiment)

## Overall Success Rates
- **Baseline**: 76.9%
- **Current Procedural (Blind)**: 61.5%
- **Gated Procedural**: 76.9%

## Overall Median Tool Calls
- **Baseline**: 5.0
- **Current Procedural**: 4.0
- **Gated Procedural**: 3.0

## Detailed Task Comparisons
| Task ID | Baseline | Blind Proc | Gated Proc | Gate Decision | Gate Reason |
|---------|----------|------------|------------|---------------|-------------|
| T1 | ✅ | ✅ | ✅ | REJECT | The retrieved procedures are either irrelevant ... |
| T2_v2 | ✅ | ✅ | ✅ | REJECT | The task is a straightforward table reading/ext... |
| T3 | ❌ | ❌ | ❌ | REJECT | The task is a straightforward zero-shot extract... |
| T4 | ✅ | ❌ | ❌ | REJECT | The candidate procedures provide only generic, ... |
| T5 | ❌ | ❌ | ❌ | REJECT | The procedures provide only generic, obvious st... |
| T6 | ❌ | ✅ | ✅ | REJECT | The candidate procedures provide only basic, ge... |
| T7 | ✅ | ✅ | ✅ | REJECT | The task is a standard, straightforward login f... |
| T8 | ✅ | ✅ | ✅ | REJECT | The task asks to extract the title of the first... |
| T9 | ✅ | ✅ | ✅ | REJECT | The task is a straightforward login form intera... |
| T10 | ✅ | ✅ | ✅ | REJECT | The task is a straightforward click-and-extract... |
| T11 | ✅ | ❌ | ✅ | REJECT | The candidate procedures provide only basic, ge... |
| T12 | ✅ | ✅ | ✅ | REJECT | The candidate procedures provide only generic, ... |
| T13 | ✅ | ❌ | ✅ | REJECT | The task only requires navigating to a URL and ... |

## Gating Impact Analysis
- **T10-like Rescue Cases Preserved (Gate=INJECT)**: 0 (Expected: 1)
- **T12/T13-like Regression/Trap Cases Avoided (Gate=REJECT)**: 2 (Expected: 2)

## Final Verdict
**B. Gating reduces regressions but benefit remains unproven**