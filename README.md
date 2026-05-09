# JobScout

Personal AI agent for job search — a hands-on project for learning AI
engineering. Built from scratch as a sequence of lessons covering structured
LLM outputs, tool use, agents, RAG, evaluations, and observability.

The end goal: a service that monitors job sources, scores match against my
profile, drafts cover letters, and queues everything for my review. No
auto-applies — every action requires explicit approval.

## Status

- ✅ **Lesson 1 — structured job parser.** Pydantic + Anthropic-compatible
  forced tool use. 4 prompt iterations on a 12-job test set; 3 successful,
  1 reverted as a regression. Iteration log:
  [`evals/lesson01_parser/ITERATIONS.md`](evals/lesson01_parser/ITERATIONS.md).
- ⏳ Lesson 2 — tool use with real job-board APIs (Greenhouse, Ashby).
- ⏳ Lessons 3–12 — agents, MCP server, RAG, evals, observability,
  production deployment.

## Stack

- Python 3.12, [`uv`](https://github.com/astral-sh/uv) for project management
- [Anthropic SDK](https://docs.claude.com/en/api/messages) — used for both
  Claude and DeepSeek (via DeepSeek's Anthropic-compatible endpoint)
- Pydantic v2 for typed contracts and tool input schemas
- Pydantic-settings for `.env` config
- PostgreSQL + pgvector planned (lessons 5+)

## Setup

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and install
git clone https://github.com/<your-username>/jobscout.git
cd jobscout
uv sync

# 3. Configure
cp .env.example .env
# Edit .env and add at least one API key (ANTHROPIC_API_KEY or DEEPSEEK_API_KEY)

# 4. Run the parser eval on the test set
uv run python evals/lesson01_parser/run.py
# Results written to evals/lesson01_parser/results/<RUN_NAME>/results.jsonl
```

To name a specific run:

```bash
RUN_NAME=v3_alternatives uv run python evals/lesson01_parser/run.py
```

## Project structure

```
src/jobscout/
  parsers/                  # job parser (lesson 1)
    job_parser.py           # forced-tool-use extraction
    types.py                # ParseResult, ParseMetadata
  prompts/
    job_parser/system.md    # versioned prompt — main artefact
  schemas.py                # domain models (JobPosting, SalaryRange)
  llm.py                    # thin Anthropic-SDK wrapper supporting
                            #   both Anthropic and DeepSeek
  pricing.py                # per-call cost calculation (Decimal)
  config.py                 # .env-driven settings

data/jobs_raw/              # 12 real job postings used as test set
evals/lesson01_parser/
  run.py                    # batch parser run — writes results.jsonl
  ground_truth.jsonl        # manually labeled expected values
  ITERATIONS.md             # iteration log: change → diff → decision
  results/<RUN_NAME>/       # one folder per run, kept as history

traces/                     # per-call traces (gitignored)
BACKLOG.md                  # known issues and deferred decisions
```

## Key design decisions

**One LLM client, two providers.** `llm.py` wraps `anthropic.Anthropic`
and routes to either Anthropic's API or DeepSeek's Anthropic-compatible
endpoint based on `LLM_PROVIDER` env. Same code, same SDK, same response
format — no abstraction layer needed.

**Structured output via forced tool use.** Pydantic model →
`model_json_schema()` → tool's `input_schema`. The LLM is forced via
`tool_choice` to call this tool, so its output is constrained to match
the schema. This is more reliable than asking for JSON in free-form prose.

**Separate domain and operational types.** `JobPosting` (domain) lives
in `schemas.py`; `ParseResult` and `ParseMetadata` (operational — tokens,
cost, latency) live in `parsers/types.py`. The two have different
lifecycles: domain goes to DB and search, metadata goes to traces and
billing dashboards.

**Per-run results directories.** Each eval run writes to
`evals/lesson01_parser/results/<RUN_NAME>/` rather than overwriting a
single file. This makes it possible to diff runs against a baseline and
keep the iteration log honest.

**Prompts as versioned files.** All prompts live as `.md` files under
`src/jobscout/prompts/`, loaded via `load_prompt()`. Each call's trace
records `system_prompt_hash`, so any past output can be tied back to a
specific prompt version via `git log`.

## Iteration log format

The iteration log (`evals/lesson01_parser/ITERATIONS.md`) is the main
project artefact for showcasing the prompt-engineering process:

- Each version: prompt change → results path → diff vs previous version
  in a count-of-errors table → decisions for next version
- Reverted versions are kept with a clear reason — failed experiments
  are part of the history

## License

MIT
