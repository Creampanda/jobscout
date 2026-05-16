# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project nature

JobScout is a learning project structured as a sequence of lessons (lesson 1 = structured job parser; lessons 2+ planned). Each lesson produces real code under `src/jobscout/` plus an iteration log under `evals/lessonNN_*/ITERATIONS.md`. The iteration log is the main artefact — prompt changes, measured diffs, and reverted experiments are kept on purpose. When adding to a lesson, update the log; don't rewrite history.

## Commands

```bash
# Install / sync deps (uv-managed, Python 3.12)
uv sync

# Run the lesson-1 parser over all postings in data/jobs_raw/
uv run python evals/lesson01_parser/run.py

# Name a run (otherwise UTC timestamp is used). Results land in
# evals/lesson01_parser/results/<RUN_NAME>/results.jsonl
RUN_NAME=v5_something uv run python evals/lesson01_parser/run.py

# Lesson 2 — smoke-test the search tool in isolation (no agent loop yet)
uv run python scripts/run_remotive.py

# Lint / typecheck / tests (dev deps; no test files exist yet)
uv run ruff check .
uv run mypy src
uv run pytest
```

Configuration: copy `.env.example` to `.env` and set `LLM_PROVIDER` (`anthropic` or `deepseek`), `LLM_MODEL`, and the matching API key. Pricing table in `src/jobscout/pricing.py` must contain an entry for whichever `LLM_MODEL` is used, or `calculate_cost` raises `UnknownModelError`.

## Architecture

**One LLM client, two providers.** `src/jobscout/llm.py` wraps `anthropic.Anthropic` and switches `base_url` between Anthropic and DeepSeek's Anthropic-compatible endpoint (`https://api.deepseek.com/anthropic`). Same SDK, same response shape — no provider abstraction layer. `thinking={"type": "disabled"}` is hardcoded because DeepSeek's `/anthropic` defaults v4-flash to thinking mode, which conflicts with forced `tool_choice` (see BACKLOG.md "Infrastructure").

**Structured output via forced tool use, not JSON-in-prose.** `parsers/job_parser.py` builds a tool whose `input_schema` is `JobPosting.model_json_schema()` and passes `tool_choice={"type": "tool", "name": "..."}`. The model is forced to call the tool; its arguments are validated by Pydantic. Schema changes in `schemas.py` automatically flow to the tool definition — no separate schema duplication.

**Domain vs operational types are deliberately separate.** `schemas.py` holds `JobPosting` / `SalaryRange` (will go to DB and search later). `parsers/types.py` holds `ParseMetadata` / `ParseResult` (tokens, cost, latency, trace path — goes to traces and billing dashboards). They have different lifecycles; do not merge them.

**Prompts are versioned files, hashed per call.** All prompts live as `.md` under `src/jobscout/prompts/`. `prompts/__init__.py` exposes `load_prompt(name)` (LRU-cached) and `prompt_hash(text)`. Every trace records `system_prompt_hash`, so any past output can be tied back to a specific prompt version via `git log` on the `.md` file. When editing a prompt, treat it as code: small focused change, then a new eval run.

**Traces are written before Pydantic validation.** In `parse_job`, the trace JSON is saved to `traces/lesson01/<timestamp>.json` *before* `JobPosting(**tool_use_block.input)` runs. This is intentional — if validation fails, the raw model output is still on disk for debugging. Don't reorder these steps. `traces/` is gitignored.

**Per-run eval results, never overwritten.** `evals/lessonNN_*/run.py` writes to `results/<RUN_NAME>/results.jsonl`. Each run is a folder, kept in git as history. This makes diffs between iterations possible and is what the iteration log references. Don't add logic that overwrites or cleans old run dirs.

**Multi-round tool use, beyond single forced call (lesson 2).** `agents/job_finder.py` (work in progress) will run a real tool-use loop with `tool_choice="auto"` — the model picks which tool to call and when to stop. Distinct from lesson 1's single forced call: `messages` accumulate across rounds and are resent in full each round; `stop_reason="end_turn"` is the natural termination. Hard cap is 8 rounds. Both patterns share the same SDK and `messages.create` call shape.

**Tool contract — typed success per tool, shared `ToolError`.** Each tool in `src/jobscout/tools/` returns its own Pydantic success model (e.g. `RemotiveJob` / `RemotiveJobsResult` in `tools/remotive.py`). Errors flow through one shared class: `tools/types.py:ToolError(error: str)`. `tools/registry.py:execute_tool` is the only place that catches expected exceptions (`httpx.HTTPError`, `pydantic.ValidationError`, `KeyError`, `ValueError`) and wraps them in `ToolError`. Unexpected exceptions are NOT caught — they crash the run, by design (cheap to fail loud in a learning project). The agent treats `"error" in result` as the signal for `is_error: True` in the `tool_result` block.

**Tool definition lives next to the function.** Every tool file defines both the callable (`search_remote_jobs`) and the Anthropic tool def (`REMOTIVE_TOOL_DEF`). `tools/registry.py` only assembles `TOOLS` (dispatch) and `TOOL_DEFINITIONS` (sent to the model on every round). Adding a new tool = one new file in `tools/` + two imports in `registry.py`. Keep the two collections in sync.

**Search tools return 500-char snippets, not full text.** Job-search tools strip HTML and truncate descriptions to 500 chars to keep token cost bounded (full Remotive `limit=50` response ≈ 16K chars ≈ 4K tokens). Full-text fetching is deferred to a later lesson; `extract_job_posting` will operate on the snippet, accepting that some `JobPosting` fields (e.g. `responsibilities`, `red_flags`) will be partial. This is a known constraint, not a bug.

## Working on a lesson iteration (lesson 1 pattern, reuse for future lessons)

1. Change exactly one thing (usually one rule in the system prompt, or one schema field).
2. Run `RUN_NAME=vN_short_slug uv run python evals/lesson01_parser/run.py`.
3. Compare against the previous run's `results.jsonl` and `ground_truth.jsonl`.
4. Add a section to `ITERATIONS.md`: prompt change → diff table (count of errors per class, vs previous version) → decisions for next version.
5. Reverted experiments stay in the log with a clear "REVERTED" marker and reason. Failed iterations are part of the artefact, not deleted.

## Current work — lesson 2 (in progress)

Full lesson 2 spec lives in `lesson02_tool_use_TZ.md` at repo root. Lesson 2 is being built as a **thin vertical slice**: get one tool (Remotive) working end-to-end through a multi-round agent before adding others. This surfaces agent-loop bugs on minimal surface area.

**Done:**

- `src/jobscout/tools/types.py` — `ToolError`.
- `src/jobscout/tools/remotive.py` — `RemotiveJob`, `RemotiveJobsResult`, `REMOTIVE_TOOL_DEF`, `search_remote_jobs(limit=50)`. Pure function, raises on error.
- `src/jobscout/tools/registry.py` — `TOOLS`, `TOOL_DEFINITIONS`, `execute_tool(name, arguments)` with narrow `except` (httpx/pydantic/Key/Value only) and unknown-tool-name handled explicitly.
- `src/jobscout/prompts/job_finder/system.md` v1 — agent system prompt, single-tool variant (search → filter → text reply; no extract yet).
- `scripts/run_remotive.py` — smoke test, confirmed: live HTTP works, Pydantic validates real Remotive response, error path returns `{"error": "..."}`, `limit=50` ≈ 16K chars.

**Pending, in order:**

1. Verify `prompts/__init__.py` supports subpath: `load_prompt("job_finder/system.md")`.
2. Confirm `llm.messages_create` returns the raw `Message` object (need `stop_reason`, `content` blocks, `usage`) — not just `.content[0].text` as lesson 1 may have done.
3. `src/jobscout/agents/types.py` — `AgentResult`, `ToolCallTrace`.
4. `src/jobscout/agents/job_finder.py` — main loop: `tool_choice="auto"`, max 8 rounds, accumulate `messages`, sum tokens via `pricing.py`, support parallel `tool_use` blocks in one round.
5. `evals/lesson02_agent/run.py` — CLI runner with `--skills`, writes `results/<RUN_NAME>/results.jsonl`, `traces.jsonl`, `summary.json`.
6. `evals/lesson02_agent/ITERATIONS.md` — start log with `v1_baseline` (Remotive only), then at least one prompt-revision iteration.
7. After thin slice works, add remaining tools per the TZ: `tools/arbeitnow.py`, `tools/wikipedia.py`, `tools/extract_job.py` (the last one wraps `parsers/job_parser.py` from lesson 1 — two-level tool use).

**Architectural decisions locked during this work (do not relitigate without reason):**

- **Error handling lives in `registry.execute_tool`, not in each tool.** Tools are pure functions that raise expected exceptions; the registry wraps them. Unexpected exceptions propagate.
- **No `error_type` categorisation on `ToolError`.** Just `error: str`. Categories add complexity without payoff at this scale.
- **Each tool owns its success Pydantic type AND its Anthropic tool def.** Shared `tools/types.py` only carries the cross-tool `ToolError`.
- **Thin vertical slice over horizontal.** Don't implement all 4 tools first — finish the agent loop on Remotive, then expand.

## Known issues — read BACKLOG.md before "fixing"

Several parser issues are deliberately deferred to lesson 8 (automated evals): "Our tech" stack bleeding into `must_have_skills`, generic-category noise, internal-level-title mapping (SE 5 → staff), missed red-flag patterns, `Golang`/`Go` canonicalization. These were tried and reverted, or are flagged as needing automated evals to fix safely. Don't ad-hoc fix them in the prompt without an eval to catch regressions — that's the lesson v4 reverted itself over.

Lesson 2 deferrals (explicit non-goals per `lesson02_tool_use_TZ.md`): no Arbeitnow pagination beyond page 1, no Python-side parallel HTTP between tool calls in a round (sequential is fine), no response caching, no deduplication across search sources (the same job may surface in both Remotive and Arbeitnow), no DB writes, no MCP server (that's lesson 4), no tool-selection-accuracy evals (lesson 8). Remotive's CDN caches responses ~24h — repeat calls in the same run return identical data and are wasteful; this is encoded both in the tool's `description` and in the agent system prompt.
