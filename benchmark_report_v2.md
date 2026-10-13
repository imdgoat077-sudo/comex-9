# Phase 12C/D Benchmark Report V2 (Corrected Instrumentation)

## Overall Metrics
- **Baseline Browser-Grounded Task Success Rate**: 75.0%
- **Procedural Browser-Grounded Task Success Rate**: 75.0%
- **Absolute Success-Rate Difference**: +0.0%

### Procedural States (Out of 12 runs)
- **A. Procedure Retrieved**: 12/12
- **B. Correct Procedure Retrieved**: 12/12
- **C. Procedure Injected**: 12/12
- **D. Behaviorally-Followed Procedure**: 10/12

### Operational Metrics (Medians)
| Condition | Tool Calls | Failed Tools | Duration (s) |
|-----------|------------|--------------|--------------|
| Baseline  | 5.0 | 0.0 | 31.8 |
| Procedural| 5.0 | 0.0 | 37.9 |

### Efficiency Analysis
- **Cases where Procedural used fewer tool calls**: 4/12
- **Cases where Procedural used fewer tool calls BUT took longer**: 0/4

## Per-Family Results
### form_submission
- Baseline: 100.0% (3/3)
- Procedural: 100.0% (3/3)
### click_detail_and_extract
- Baseline: 66.7% (2/3)
- Procedural: 66.7% (2/3)
### extract_list_items
- Baseline: 66.7% (2/3)
- Procedural: 66.7% (2/3)
### search_and_extract
- Baseline: 66.7% (2/3)
- Procedural: 66.7% (2/3)

## Per-Task Results
| Task ID | Family | Baseline | Procedural | Delta |
|---------|--------|----------|------------|-------|
| T1 | extract_list_items | ✅ | ✅ | ➖ Equal (Pass) |
| T2_v2 | extract_list_items | ✅ | ✅ | ➖ Equal (Pass) |
| T3 | extract_list_items | ❌ | ❌ | ➖ Equal (Fail) |
| T4 | search_and_extract | ✅ | ✅ | ➖ Equal (Pass) |
| T5 | search_and_extract | ❌ | ❌ | ➖ Equal (Fail) |
| T6 | search_and_extract | ✅ | ✅ | ➖ Equal (Pass) |
| T7 | form_submission | ✅ | ✅ | ➖ Equal (Pass) |
| T8 | form_submission | ✅ | ✅ | ➖ Equal (Pass) |
| T9 | form_submission | ✅ | ✅ | ➖ Equal (Pass) |
| T10 | click_detail_and_extract | ❌ | ✅ | 📈 Improved |
| T11 | click_detail_and_extract | ✅ | ✅ | ➖ Equal (Pass) |
| T12 | click_detail_and_extract | ✅ | ❌ | 📉 Regressed |

## Behavioral Evidence Trace (Procedural Runs)
- **T8**: ✅ Followed (Tool Calls: 9)
- **T7**: ✅ Followed (Tool Calls: 5)
- **T9**: ✅ Followed (Tool Calls: 4)
- **T4**: ✅ Followed (Tool Calls: 6)
- **T1**: ✅ Followed (Tool Calls: 6)
- **T2_v2**: ✅ Followed (Tool Calls: 5)
- **T10**: ✅ Followed (Tool Calls: 3)
- **T3**: ✅ Followed (Tool Calls: 5)
- **T5**: ❌ Diverged (Tool Calls: 2)
- **T12**: ❌ Diverged (Tool Calls: 2)
- **T6**: ✅ Followed (Tool Calls: 3)
- **T11**: ✅ Followed (Tool Calls: 5)

## Final Verdict
**B. PROCEDURAL MEMORY RETRIEVES CORRECTLY BUT BENEFIT IS NOT YET SHOWN**