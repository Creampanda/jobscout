# JobScout Backlog

Known issues, deferred decisions, and ideas, ordered by likely lesson where
they'll be addressed.

## Open issues — to address in lesson 8 (automated evals)

### Stack section bleeds into must_have_skills

The parser conflates "Our tech" / "Stack" sections (which describe what
the team uses) with "Requirements" / "Qualifications" sections (which
describe what the candidate needs to have).

**Example:** Metriport's "Senior Software Engineer.txt" lists
`["React", "Node.js", "TypeScript", "DynamoDB", "Snowflake", "FHIR"]`
in must_have, but the actual Requirements section says only
"6+ years full-stack experience with backend lean" + "cloud-based platforms"
+ "infra as code". The team's tech stack is bonus knowledge,
not a requirement.

**Why it matters:** downstream Evaluator (lesson 5) will incorrectly
disqualify candidates who don't know Snowflake/FHIR specifically,
even though the posting accepts general full-stack experience.

**Possible fixes:**

- Add field `team_stack: list[str]` separate from `must_have_skills` —
  schema-level distinction
- Prompt rule with explicit detection: "if a list of techs appears under
  'Our tech', 'Stack', 'We use' → put in `team_stack`, not must_have"
- LLM-as-judge eval: "for each item in must_have, find the verbatim
  source sentence; flag entries from Tech/Stack sections"

### Generic categories — context-dependent

"Full-stack engineering", "backend engineering", "cloud-native tooling"
are sometimes legitimate requirements ("you should be a full-stack
engineer") and sometimes noise ("we use full-stack approach").

**Attempted in v4 of lesson 1, reverted** — keyword-matching exclusion
killed legitimate cases. Needs a context-aware approach.

**Possible fixes:**

- LLM-as-judge eval that checks each must_have entry against the source
  sentence and flags entries that come from descriptive context, not
  requirement context
- Rephrase rule to ask the model to retain the surrounding sentence as
  evidence; reject entries with no concrete tech anchor

### Internal company titles not mapped to standard levels

Nextdoor "Software Engineer 5" parsed as `senior`, expected `staff`.
Same applies to "IC4", "E6", "SDE III" patterns.

**Possible fix:** add prompt rule with mapping table (E5/IC5/SE5 = staff,
E6/IC6 = principal). Validate against ~$compensation as confirmation.

### Red flags missed: hype-language and cheap-labor-only regions

Bold Business posting compresses three senior roles into one (architect +
builder + standard-setter), no salary, lists only India/LATAM/Philippines
as eligible regions. None of this triggered red_flags in v3.

**Possible fixes:**

- Add red flag pattern: "multiple senior roles compressed into one"
- Add red flag pattern: "compensation only available in low-cost regions"
- Add red flag pattern: "hype language without specifics"

### `Golang` vs `Go` — name canonicalization

Same language appears as `Go` in must_have and `Golang` in nice_to_have
within the same posting.

**Possible fix:** post-processing dictionary (Golang→Go, JS→JavaScript,
TS→TypeScript, etc.) applied to both fields.

## Infrastructure

### DeepSeek `/anthropic` endpoint thinking-mode incompatibility

DeepSeek's Anthropic-compatible endpoint defaults v4-flash to thinking
mode, which rejects forced `tool_choice`. The SDK sends
`thinking: false` (boolean), but the server expects
`{"type": "disabled"}` (object).

**Workaround for now:** explicit `thinking={"type": "disabled"}` in the
LLM client when provider is `deepseek`. Currently using Claude Haiku 4.5
for lesson 1 to avoid the issue.

**Revisit:** lessons 5/10 when cost optimization matters — DeepSeek is
~10× cheaper for high-volume scoring.

## Lesson 2 — deferred follow-ups

### Seed user message hard-codes "remote jobs"

`agents/job_finder.py:23` always starts the conversation with
`"Find relevant remote jobs for skills: ..."`. The word "remote" in the
user turn overrides the more liberal system-prompt rules — v2 of the
prompt relaxed Arbeitnow's remote-only filter, but the agent still
produced zero onsite Arbeitnow jobs because of this user-turn framing.

**Fix options:**

- Change the seed to `"Find relevant jobs for skills: ..."` — one-line fix.
- Add CLI flag `--work-format remote|hybrid|any` and template the user
  message based on it.

**Why deferred:** lesson 2's DoD (loop works + one measurable iteration)
is met; this is a feature decision tied to lesson 2.5 (resume / profile
filtering) where work format becomes part of the user profile anyway.

### Remotive — no targeted search

`search_remote_jobs` calls `GET /api/remote-jobs` and returns the first
`limit` of the unfiltered CDN cache (~18 jobs in practice). The Remotive
API supports `?search=<query>` and `?category=<id>` server-side. Right
now the agent filters from a ~18-job random pool, not a query-targeted
one.

**Fix:** add an optional `search: str | None` arg to
`search_remote_jobs` and forward to the API; update the tool's
`input_schema` so the agent passes the user's primary skill.

**Why deferred:** lesson 2 is about the agent loop, not search quality.
Picks up naturally in lesson 2.5 or wherever search-quality evals live.

### Arbeitnow — server-side filters (mostly absent)

Empirically verified 2026-05-19 against
`https://www.arbeitnow.com/api/job-board-api`:

- `?page=<n>` — works (documented).
- `?visa_sponsorship=true` — works (real filter; reduces ~100 → ~4).
- Ignored silently: `remote`, `tags`, `tag`, `search`, `query`, `q`,
  `location`. Returns the same 100-job page as baseline.

**Implication:** filtering by skills and remote-ness must stay
client-side (prompt-driven). Don't re-probe; if Arbeitnow ever adds real
filters they'll show up in `meta.info` of the response.

The non-goal "no pagination beyond page 1" stands, but combined with the
no-server-filter reality, Arbeitnow's effective contribution to a
`--skills python` shortlist is ~3 jobs/run. Revisit if Arbeitnow becomes
load-bearing.

### Third skill-set run not executed

Lesson 2's DoD asks for 3 different `--skills` sets. Only `python` was
exercised across `v1_baseline` and `v2_arbeitnow_no_remote_filter`. The
cycle is mechanically identical regardless of skill set — coverage gap,
not a bug.

### `extract_job_posting` outputs not dumped to disk per run

`run_job_finder(..., dump_dir=...)` writes `remotive_raw.json` /
`arbeitnow_raw.json` for the search tools but skips
`extract_job_posting`. Its outputs are already in `results.jsonl` (as
`ExtractedJob`), so a second copy would be redundant. Logged as a
deliberate decision, not a TODO.

## Schema improvements (lesson 5+)

### Multilingual support

Currently parser is English-output-only; postings in Russian/German get
translated. Track language in the schema and decide at downstream level
how to handle.

**Add:** `language: Literal["en", "ru", "de", "other"]` field.

### Separate fields for soft requirements / responsibilities

Currently soft skills and responsibilities are dropped entirely. They are
real signals (e.g., "manage team of 5" tells you about scope) but don't
belong in `must_have_skills`.

**Add (later):** `responsibilities: list[str]`, `team_size: int | None`.
