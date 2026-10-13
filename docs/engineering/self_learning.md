# Self-learning memory (Phase B)

Folder: `Comex copy 19 - Cursor Multi - 2`. Code: `graph/learning.py`, `graph/store.py` (Lesson methods),
`graph/schema.py` (v5), `services/chat_store.py` (compaction status), `agent_service.py` (recall, evidence, reflection,
compactor). Tests: `tests/test_self_learning.py`.

## Goal

Comex should get better at the sites you use: when it fights its way through something hard on a site (a hidden
editor, a slow table, a login wall), the next run on that site should know what worked, without a slower run and
without filling memory with noise.

## Layers

| Layer | Store | Written | Read |
|---|---|---|---|
| Conversation transcript | SQLite `~/.comex/chats.db` | every turn, as it happens | the parent agent's bounded history |
| Conversation summary | Kùzu `Artifact` (`convsum_<conversation>`) | once, when the chat closes (compaction) | `search_memory` |
| User facts | Kùzu `UserMemory` (one per category+key) | reflection and compaction, filtered | every run (top 8) |
| Lessons (obstacle -> what worked -> avoid) | Kùzu `Lesson`, per site | reflection after a *difficult* run | runs on that site (top 3) |
| Skills (reusable procedure) | Kùzu `Skill`, per site | reflection | runs on that site (top 3) |
| Traps (failed selectors) | Kùzu `AntiPattern`, per site | tool failures | runs on that site (top 3) |

## The loop

1. **Recall (start of a run, no model call).** The site is taken from the page in the agent's tab (a worker: its start
   page). Lessons, skills and traps for that site are offered, marked as data that may be outdated. The ids offered
   are recorded on the run. *Before this phase the site came from the browser's debugging address, so site memory was
   only found when the task text named the site.*
2. **Act.** Unchanged.
3. **Evidence (end of a run, no model call).** Offered lessons and skills are credited when the run completes and
   debited when it fails. A lesson that has failed 3 times, and more often than it helped, is demoted: kept, never
   offered. Learning it again gives it a fresh record on probation; its next success makes it active.
4. **Reflection (background, one model call, only when useful).** Skipped for chat replies with no actions, and for
   workers unless their run was difficult. "Difficult" is a rule over the run's own record: 2+ failed actions, 12+
   actions, 3+ sites, or running out of time/actions. Only then does the reflection write a lesson
   `{site, obstacle, approach, avoid}`. A lesson on the same obstacle (word overlap >= 50%) refines the existing one.
5. **Compaction (background, one model call per finished chat).** When a chat's last tab closes, or "new chat" closes
   it, the transcript is summarised into a `conversation_summary` artifact and durable user facts. The status column
   moves pending -> done only after the graph writes, ids are fixed, and facts are upserted by key, so a crash or a
   repeat never duplicates memory; pending work is resumed at startup. Failed attempts are retried on the next start
   (at most 3 times per process).

## Noise control

- User facts must be facts the *user* stated; keys about paths, folders, usernames, machines are dropped (earlier
  runs stored the home folder and the login name as "user memory").
- Memory ids are stable across restarts (sha1, not Python's salted `hash()`); existing nodes are matched by their
  natural key first, so older ids are reused instead of duplicated.
- Sites are stored without `www.`; recall matches both forms for older entries.

## Why no vector database (yet)

- Recall is keyed by *site* first; within one site there are a handful of lessons and skills. Word overlap and
  evidence ranking separate them well at that size.
- Vectors need an embedding model: another network call (or a local model and new dependency) on every save and
  every run start. Measured model latency through the router is ~3 s per call; even a fast embedding call would add
  more time than it can save here.
- If it becomes necessary (hundreds of lessons per site, or measured misses on paraphrased obstacles), Kùzu 0.11
  already has a built-in vector index, so it would be a column plus an index on `Lesson`/`Skill`, not a new database.
  Measure first: log recall hits versus lessons that would have applied.

## Recall beyond the site (Phase C, `graph/recall.py`)

- Every run, parent and workers, gets one recall pass before the first model call: a few local full-text searches,
  no model call. The run records it in `metadata["memory_recall"]` and `timing["memory_recall_ms"]`.
- Query = the task's content words (a worker uses its objective and the user's request, not its whole brief) + the
  site's name + the previous turn's words when the task is a short or referential follow-up ("add that to the cart").
- Without a memory phrase ("previously", "last time", ...) only durable memory is searched (saved reports, summaries of
  earlier chats, extracted items, user facts), and a result is kept only if it shares at least two query words.
  With one, past tasks and tool results are searched too (the Phase 10 behaviour).
- Procedure artifacts are never recalled here: they have their own gated retrieval, and Phase 14 showed they add noise.
- `search_memory` has a `LESSONS` domain (demoted lessons hidden). When every match is already in the prompt it says
  so instead of "no memory", so the model does not deny memory it was shown.
- Workers may use memory as a hint about where to look; they report only facts seen on a page in this run.
