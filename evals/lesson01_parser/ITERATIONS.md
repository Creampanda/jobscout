# Lesson 1 — Job Parser Iteration Log

Test set: 12 real job postings in `data/jobs_raw/` covering Backend/Full-Stack/
Staff/Lead roles, mostly remote, mix of clear and ambiguous postings.

Ground truth: `ground_truth.jsonl` — manually labeled expected values for
`level`, `remote`, `salary_present`, `red_flags` count range.

Provider: Anthropic Claude Haiku 4.5 (DeepSeek `/anthropic` endpoint had
incompatibility with forced tool_choice — see BACKLOG.md).

**Final state:** lesson 1 closed at **v3**. v4 was reverted as a regression.

---

## v1: baseline — 2026-05-08

**Prompt commit:** _fill manually with `git log` history of `src/jobscout/prompts/job_parser/system.md`_
**Results:** `results/baseline/results.jsonl`

### Initial state

First version of the system prompt with manual rules for level detection,
red_flags categories, and must-have/nice-to-have distinction. Three
few-shot examples in the prompt.

### Manual review — error classes

| Class of error                                                                | Count | Severity |
| ----------------------------------------------------------------------------- | ----- | -------- |
| Soft skills / responsibilities in `must_have`                                 | 5/12  | High     |
| `or` interpreted as `and` (e.g., Stripe "Ruby, Go, or Java")                  | 1/12  | Medium   |
| Internal level titles missed (e.g., Nextdoor "SE 5" → senior, expected staff) | 1/12  | Medium   |
| Red flags missed: hype-language, cheap-labor-only regions                     | 3/12  | Medium   |
| Categories instead of techs in `must_have` ("cloud-native tooling")           | 1/12  | Low      |
| Education ("CS degree") in `must_have_skills`                                 | 1/12  | Low      |

### Decisions for v2

Address top class first: clean up `must_have_skills` to be tech-only.

---

## v2: must_have_skills tech-only — 2026-05-08

**Prompt commit:** _fill manually_
**Results:** `results/v2_must_have_cleanup/results.jsonl`

### Prompt change

Added new rule #3 to `system.md`: "must_have_skills and nice_to_have_skills
contain ONLY technical skills". Listed explicit exclusions (soft skills,
responsibilities, education, years of experience).

### Diff vs v1

| Class of error                                | v1   | v2   | Status                                                                                       |
| --------------------------------------------- | ---- | ---- | -------------------------------------------------------------------------------------------- |
| Soft skills / responsibilities in `must_have` | 5/12 | 0/12 | ✅ Fixed                                                                                      |
| Education in `must_have_skills`               | 1/12 | 0/12 | ✅ Fixed                                                                                      |
| `or` interpreted as `and`                     | 1/12 | 3/12 | ⚠️ Surfaced more cases (likely measurement, not regression — re-counted v1 with stricter eye) |
| Internal level titles missed                  | 1/12 | 1/12 | Unchanged                                                                                    |
| Red flags missed                              | 3/12 | 3/12 | Unchanged                                                                                    |
| Categories in `must_have`                     | 1/12 | 2/12 | ⚠️ Slightly worse                                                                             |

### Decisions for v3

Address `or`-as-`and` next — it's the most actionable problem and the Stripe
test case provides clear ground truth.

---

## v3: alternatives encoded as "X OR Y OR Z" — 2026-05-08

**Prompt commit:** _fill manually_
**Results:** `results/v3_alternatives/results.jsonl`

### Prompt change

Replaced previous weak rule (which mentioned specific languages) with a full
"Handling alternatives" section: detection signals (or, one of, at least one,
any of, such as), encoding rule (single skill with " OR " separator,
uppercase), and explicit counter-example (comma-separated without "or" =
all required).

Added Example 4 to `system.md` Examples section.

### Diff vs v2

| Class of error                  | v2   | v3   | Status                      |
| ------------------------------- | ---- | ---- | --------------------------- |
| `or` interpreted as `and`       | 3/12 | 0/12 | ✅ Fixed                     |
| Soft skills in `must_have`      | 0/12 | 0/12 | Stable                      |
| Education in `must_have_skills` | 0/12 | 0/12 | Stable                      |
| Internal level titles missed    | 1/12 | 1/12 | Unchanged                   |
| Red flags missed                | 3/12 | 3/12 | Unchanged                   |
| Categories in `must_have`       | 2/12 | 3/12 | ⚠️ Worse — main issue for v4 |

### Detected alternatives (sanity check)

Verified output across the 5 jobs that contain alternatives:

- Stripe: `["Ruby OR Go OR Java", ...]` ✅
- Software Engineer 3: `["Go OR C# OR Java OR Kotlin OR Rust", ...]` ✅
- Senior Full Stack: 3 separate OR-groups detected correctly ✅
- Lead Backend: `["NodeJS OR Ruby OR Golang OR Python", ...]` ✅
- Remote Product Engineer: `["Go OR TypeScript OR React OR comparable tools"]` — note "comparable tools" included as 4th alternative, debatable

### Decisions for v4

Generic categories ("full-stack engineering", "software design patterns",
"cloud-native tooling") still appearing in must_have. Try a specificity
rule that lists categories to exclude.

---

## v4: skill specificity (REVERTED) — 2026-05-09

**Prompt commit:** _fill manually_
**Results:** `results/v4_specificity/results.jsonl`

### Prompt change

Added "Specificity requirement" rule listing generic categories to exclude
("full-stack engineering", "software design patterns", "cloud-native tooling").

### Diff vs v3

| Class of error                                       | v3   | v4   | Status                       |
| ---------------------------------------------------- | ---- | ---- | ---------------------------- |
| Generic categories in must_have                      | 3/12 | 0/12 | ✅ Fixed                      |
| Legitimate "full-stack" skills lost                  | 0/12 | 2/12 | ❌ NEW REGRESSION             |
| "Our tech" stack incorrectly classified as must_have | 1/12 | 1/12 | Unchanged — separate problem |

### Decision: REVERT

The "specificity" rule was too aggressive. Pattern-matching by keyword
("if you see 'full-stack engineering' — exclude") fails to distinguish:

- "we use full-stack engineering principles" (description, exclude is fine)
- "you should be a full-stack engineer with backend lean" (legitimate
  requirement, exclude breaks the result)

The model has no way to make this distinction from a static keyword list.
This problem requires either:

(a) more nuanced rules with semantic context that the model evaluates, or
(b) automated evals that catch regressions before they ship — so we can
    afford to try aggressive rules and roll back what doesn't work.

Lesson 1 closed at v3. v4 prompt change reverted; results kept as
historical evidence of the failed experiment. Remaining issues
consolidated in BACKLOG.md for systematic resolution in lesson 8.

---

## Final state — v3

Lesson 1 closed at v3. Closed error classes:

- ✅ Soft skills/responsibilities in must_have (v2)
- ✅ Education in must_have_skills (v2)
- ✅ "X or Y" alternatives wrongly grouped as AND (v3)

Open error classes (deferred to lesson 8 with automated evals):

- "Our tech" stack section incorrectly merged into requirements
- Generic categories ("full-stack engineering") sometimes appropriate, sometimes noise — needs context-aware detection
- Internal company titles (SE 5, IC4) not mapped to standard levels
- Red flags missed: hype-language without specifics, cheap-labor-only regions
- `Golang` vs `Go` name canonicalization

---

## Lesson takeaways

- 4 prompt iterations attempted; 3 of them improved the parser, 1 was
  reverted as a regression.
- Each iteration: 1 rule change → 1 evaluation run → measured diff.
- Total cost across all 4 runs: ~$0.20 on Claude Haiku 4.5.
- The reverted v4 is the most valuable lesson: manual eval on 12 jobs is
  not sensitive enough to catch nuanced regressions. Automated evals
  (lesson 8) will let me try aggressive rules and roll back fast.
- Prompt grew from ~80 to ~140 lines. Each addition closed a measurable
  class of errors; v4's addition also created one.
