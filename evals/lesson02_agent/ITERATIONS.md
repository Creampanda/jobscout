# Lesson 2 — Job Finder Agent Iteration Log

Multi-round tool-use agent that searches remote/European job boards, filters by
relevance to a user-provided skill set, and extracts a structured shortlist via
the lesson 1 parser.

Tools available to the agent (`src/jobscout/tools/registry.py`):

- `search_remote_jobs` — Remotive, `limit=50`, 500-char snippets.
- `search_european_jobs` — Arbeitnow, page 1 only.
- `extract_job_posting` — wraps `parsers.job_parser.parse_job` (lesson 1).
  Expensive (own LLM call); intended for a 3–7 item shortlist.

Loop contract (`src/jobscout/agents/job_finder.py`):

- `tool_choice={"type": "auto"}`, `max_rounds=8`, accumulate `messages` across
  rounds, sum usage per round via `pricing.calculate_cost`.
- `stop_reason == "end_turn"` → take final text block, stop.
- `stop_reason == "tool_use"` → append assistant message with full `content`,
  execute every `tool_use` block, append a user message with `tool_result`
  blocks (content = JSON string, `is_error` from `"error" in result`).
- Other `stop_reason` → record it and stop.

Output per run: `results/<RUN_NAME>/{results.jsonl, traces.jsonl,
summary.json, remotive_raw.json, arbeitnow_raw.json}`. The two `*_raw.json`
files are the tool dumps (model_dump after Pydantic validation, with the
500-char snippet truncation as the agent saw it).

Provider: DeepSeek v4-flash via `/anthropic` endpoint.

---

## v1: baseline — 2026-05-19

**Prompt:** `src/jobscout/prompts/job_finder/system.md`, hash `5a3117c6`
**Command:** `RUN_NAME=v1_baseline uv run python evals/lesson02_agent/run.py --skills python`
**Results:** `results/v1_baseline/`

### Numbers

| Metric            | Value                                                          |
| ----------------- | -------------------------------------------------------------- |
| Rounds used       | 3 / 8                                                          |
| Stop reason       | `end_turn`                                                     |
| Tool calls        | `search_remote_jobs` ×1, `search_european_jobs` ×1, `extract_job_posting` ×3 |
| Jobs extracted    | 3                                                              |
| Input tokens      | 36,351                                                         |
| Output tokens     | 2,009                                                          |
| Total cost        | $0.006722                                                      |

### Observations

- Cycle works end-to-end: discover → filter (pure reasoning) → extract → end_turn.
  Hard `max_rounds` budget not approached.
- Both search tools called **in parallel in round 0** (two `tool_use` blocks in
  one assistant turn). The agent loop handles parallel `tool_use` correctly:
  one `tool_result` per `tool_use_id` in the next user message.
- `extract_job_posting` called 3× **in parallel in round 1** — agent followed
  the "prefer parallel" rule from the prompt.
- Round 2: clean text-only `end_turn` reply.
- Remotive returned 18 jobs (its CDN's effective cap; `limit=50` doesn't help —
  the cache holds ~20). Arbeitnow returned 100. The agent reasoned over a
  118-job pool and shortlisted 3 — well under the 7-call extract budget.
- **All 3 extracted jobs are from Remotive.** Zero from Arbeitnow.

### Why no Arbeitnow jobs in the shortlist

Diagnosed against the saved `arbeitnow_raw.json`-equivalent dump
(`arbeitnow_jobs.json` at repo root, captured during smoke-test):

- 100 jobs on page 1 → only **14 with `remote: true`** at peak (3 at the time
  of the first run — varies by hour as the API surfaces fresh jobs).
- Of those `remote: true` entries, **0 mention "python"** in title or
  description. The closest tech matches were Customer Support, Marketing,
  AI/ML roles in Munich (all onsite).
- Conclusion: this is not an agent bug. With the prompt rule "Arbeitnow —
  keep only `remote: true`" and `--skills python`, the intersection is
  empirically empty.

### Decisions for v2

Relax the Arbeitnow remote-only rule. The user (job-scout's owner) is open to
onsite/hybrid German roles being surfaced — they just need to be flagged as
such in the final reply. This is a deliberate scope expansion, not a fix.

---

## v2: drop Arbeitnow "remote only" filter — 2026-05-19

**Prompt:** `src/jobscout/prompts/job_finder/system.md`, hash `4aa2e78e`
**Command:** `RUN_NAME=v2_arbeitnow_no_remote_filter uv run python evals/lesson02_agent/run.py --skills python`
**Results:** `results/v2_arbeitnow_no_remote_filter/`

### Prompt change vs v1

- "Relevance criteria → Fully remote only" header removed. Arbeitnow now
  accepts remote/hybrid/onsite. Agent instructed to note the format in the
  final reply.
- Anti-pattern bullet "Don't extract onsite/hybrid Arbeitnow jobs" removed.
- Nothing else touched.

### Numbers

| Metric            | v1     | v2     | Δ     |
| ----------------- | ------ | ------ | ----- |
| Rounds used       | 3      | 3      | =     |
| Stop reason       | end_turn | end_turn | = |
| Search tool calls | 2      | 2      | =     |
| Extract calls     | 3      | 3      | =     |
| Jobs extracted    | 3      | 3      | =     |
| Total cost        | $0.006722 | (similar) | ≈ |
| Arbeitnow jobs in shortlist | 0 | **0** | **=** |

### Key finding — system_prompt vs user_message conflict

The prompt-hash changed (`5a3117c6` → `4aa2e78e`), confirming the new system
prompt was actually loaded. But the agent picked the **exact same 3 Remotive
jobs** as v1. Investigation:

- `agents/job_finder.py:23` hard-codes the initial user message as:

  ```python
  f"Find relevant remote jobs for skills: {', '.join(skills)}"
  ```

- That `"remote jobs"` phrase, sitting in the *user turn*, is a stronger
  signal than the relaxed *system* rule. The model resolved the conflict by
  trusting the user-turn framing.

Confirmed by inspection of Arbeitnow's page 1 raw dump:

- 3 jobs mention "python" anywhere. All 3 are **Munich onsite**, `remote: false`.
- Under the v2 system prompt these are valid candidates. The agent saw them
  and rejected them anyway — the user-message override is doing the work.

### Decisions for v3 (DEFERRED — explicitly chose not to do it now)

Two paths to actually unlock onsite Arbeitnow jobs:

- **A.** Change the seed user message to `"Find relevant jobs for skills: ..."`
  (drop the word "remote"). One-line fix in `job_finder.py`.
- **B.** Add a CLI flag `--work-format remote|hybrid|any` and template the
  user message accordingly. Cleaner but adds surface area.

The owner chose to leave both for now — the lesson-2 goal was "the loop works
end-to-end with a measurable iteration", which is met. The user-message
override is logged here as a known constraint, not a TODO.

### What v2 actually demonstrated

- The iteration *loop* works: prompt edit → rerun → diffable artefacts (new
  hash, separate run folder, raw dumps for inspection).
- Negative result is a real result: relaxing the system prompt alone is
  insufficient when a contradictory user-turn instruction is in play.
  Documenting this is the iteration's value, not a regression.

---

## Out of scope for lesson 2 — see BACKLOG.md

- 3rd skill-set run (`go,kafka` / frontend / ML) — DoD asks for 3 different
  skill sets, only `python` exercised. The cycle is mechanically the same;
  marked as a follow-up rather than a blocker.
- User-message refactor (v3 above).
- Server-side search for Remotive (`?search=<query>`) — currently only the
  generic ~18-job CDN cache is hit.
- Arbeitnow pagination — explicit non-goal per `lesson02_tool_use_TZ.md`.
