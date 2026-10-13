# Recalculated Phase 12C/D Benchmark Report (Strict Validation)

## Overall Metrics
- **Baseline Task Success Rate**: 66.7%
- **Procedural Task Success Rate**: 75.0%
- **Absolute Success-Rate Difference**: +8.3%

### Procedural Retrieval States (Out of 12 runs)
- **Procedure Retrieved**: 12/12
- **Correct Procedure Retrieved**: 12/12
- **Procedure Injected**: 12/12
- **Evidence of Procedure-Following**: Inferred from reduced median tool calls (4.5 vs 7.0), but absolute causal behavioral trace mapping is required for definitive proof.

### Operational Metrics (Medians)
| Condition | Tool Calls | Failed Tools | Duration (s) |
|-----------|------------|--------------|--------------|
| Baseline  | 7.0 | 1.0 | 32.9 |
| Procedural| 4.5 | 1.0 | 38.8 |

## Per-Family Results (Fixed Benchmark Family)
### extract_list_items
- Baseline: 33.3% (1/3)
- Procedural: 66.7% (2/3)
### search_and_extract
- Baseline: 66.7% (2/3)
- Procedural: 66.7% (2/3)
### form_submission
- Baseline: 100.0% (3/3)
- Procedural: 100.0% (3/3)
### click_detail_and_extract
- Baseline: 66.7% (2/3)
- Procedural: 66.7% (2/3)

## Per-Task Results
| Task ID | Family | Baseline | Procedural | Delta |
|---------|--------|----------|------------|-------|
| T1 | extract_list_items | ✅ | ✅ | ➖ Equal (Pass) |
| T2 | extract_list_items | ❌ | ✅ | 📈 Improved |
| T3 | extract_list_items | ❌ | ❌ | ➖ Equal (Fail) |
| T4 | search_and_extract | ✅ | ✅ | ➖ Equal (Pass) |
| T5 | search_and_extract | ❌ | ❌ | ➖ Equal (Fail) |
| T6 | search_and_extract | ✅ | ✅ | ➖ Equal (Pass) |
| T7 | form_submission | ✅ | ✅ | ➖ Equal (Pass) |
| T8 | form_submission | ✅ | ✅ | ➖ Equal (Pass) |
| T9 | form_submission | ✅ | ✅ | ➖ Equal (Pass) |
| T10 | click_detail_and_extract | ❌ | ❌ | ➖ Equal (Fail) |
| T11 | click_detail_and_extract | ✅ | ✅ | ➖ Equal (Pass) |
| T12 | click_detail_and_extract | ✅ | ✅ | ➖ Equal (Pass) |