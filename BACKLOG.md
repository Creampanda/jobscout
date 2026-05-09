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
