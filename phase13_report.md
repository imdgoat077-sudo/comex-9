# Phase 13 — Automatic Procedure Induction

## A. Implementation Summary
Implemented the core `run_offline_induction` logic (`induction.py`). This performs an explicit, offline sweep over the graph database to detect successful `Episode` records, abstract their concrete DOM workflows into generalizable procedures via LLM, and persist those procedures back to the graph as `Artifact` nodes with `artifact_type = "procedure"`. 
No structural changes were made to the graph schema. No automatic induction loops were added to the live agent execution path. No embeddings were introduced.

## B. Execution Flow
1. **Source Episode**: Fetch all `Episode` nodes with `outcome_status = 'completed'`.
2. **Eligibility**: A fast pre-filter runs over the task description and ToolCall trace to reject one-off requests.
3. **Induction**: The trace is serialized into an LLM prompt. The LLM converts the concrete actions into an abstract schema.
4. **Validation**: The JSON is parsed manually and required schema keys are enforced.
5. **Deduplication**: `search_procedures()` performs lexical Search on the Graph DB to verify no functionally identical capability exists.
6. **Persistence**: `graph_store.save_artifact()` is invoked. The resulting JSON payload containing the procedure and its precise provenance is stored as `Artifact.content`, explicitly linked to the source Agent node.

## C. Eligibility Rules
Episodes qualify if:
- They successfully completed (`outcome_status = 'completed'`).
- They utilize the `run_browser_harness` tool (indicating a concrete web interaction occurred).
- The prompt does not match trivial factual lookup keywords (e.g., "current price", "just checking").
- The LLM determines the trace contains a reusable workflow structure rather than a trivial single-step extraction.

## D. Induction Schema
Required JSON schema output:
- `title`: Short descriptive title
- `capability`: Short capability key (e.g. `ecommerce_checkout`)
- `goal`: Abstract goal
- `preconditions`: List of prerequisites (e.g., "User credentials are available")
- `ordered_steps`: List of abstract steps
- `applicability_notes`: When does this apply?
- `limitations_caveats`: Any limitations?

If any field is missing, or if the LLM output is malformed, the pipeline fails closed (Status: `REJECTED_INDUCTION`).

## E. Abstraction Examples
**Concrete Trace:**
- `fill username "bob", fill pass "123", click #login`
- `click .cart-icon, click .checkout`
- `fill address "123 Fake St", fill card "4444", click .submit-order`

**Induced Procedure (`ecommerce_checkout`):**
- *Navigate to the login interface, input the username and password, and submit the login form.*
- *Verify successful login and locate the shopping cart icon or link in the navigation bar.*
- *Click the cart icon to view the current cart contents, then proceed by clicking the checkout button.*
- *Fill out the required billing and shipping information on the checkout form.*
- *Enter the payment details and submit the order.*

*Notice that "bob", "123 Fake St", and "#login" were successfully stripped.*

## F. Rejected Examples
- **ep_value_lookup** (Task: "What is the current price of Bitcoin?"): Rejected by the eligibility filter due to matching keyword 'current price'.
- **ep_fail** (Task: "Extract list"): Rejected because `outcome_status = 'error'`.
- **ep_list_ext** (Task: "Extract all book titles"): Rejected during LLM Induction with reasoning: *"The execution trace is insufficient and represents a trivial single-step DOM extraction rather than a reusable multi-step procedural workflow."*

## G. Deduplication Behavior
The system invokes `check_duplicate()`, utilizing the graph's native FTS index across `Artifact` nodes. If a candidate procedure's `capability` exactly matches a stored procedure returned by the lexical search threshold, it is skipped (`REJECTED_DUPLICATE`) to prevent graph pollution.

## H. Provenance
Every successfully persisted procedure embeds a `provenance` dictionary natively in the `Artifact` content:
```json
"provenance": {
  "source_episode_id": "ep_multi_form",
  "source_agent_id": "ag_multi_form",
  "original_task": "Login to demo site, go to cart, and complete checkout",
  "induction_model": "ag/gemini-3.7-flash-medium"
}
```
Furthermore, the database maintains a native `:CREATED_ARTIFACT` link between the `Agent` node (which executed the `ToolCalls`) and the generated `Artifact` node.

## I. Test Results
- **1. successful eligible procedural episode** → Candidate produced (Passed)
- **2. factual-only episode** → Rejected (Passed)
- **3. failed episode** → Rejected (Passed)
- **4. insufficient trace** → Rejected (Passed)
- **6. concrete values are abstracted away** → Passed
- **7. reusable method is preserved** → Passed
- **8. malformed LLM output** → Rejected and not persisted (Passed)
- **9. missing required induction field** → Rejected (Passed)
- **10. provenance links back to source Episode** → Passed
- **11. duplicate procedure** → Not duplicated (Passed)
- **12. persisted procedure can be retrieved afterward** → Passed
- **13. induction does not modify the live agent execution path** → Passed
- **14. induction is explicitly invoked, not automatically executed** → Passed
- **15. original source Episode/ToolCall history remains unchanged** → Passed

## J. Limitations
1. Deduplication currently relies on strict lexical matching and capability string matching; it will fail to catch semantically identical workflows described with entirely different vocabulary.
2. We have no feedback mechanism to measure whether an induced procedure *actually* transfers successfully to a future task. 
3. The LLM abstraction can sometimes be overly aggressive in stripping out useful domain knowledge.

## K. Not yet implemented
Explicitly list:
- automatic live induction
- validation of transfer usefulness
- refinement (Phase 14)
- ranking (Phase 15)
- embeddings/vector search
- Strategy nodes
