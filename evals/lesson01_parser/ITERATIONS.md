# Lesson 1 — Job Parser Iteration Log

## v1: baseline — 2026-05-08

**Prompt:** initial version (see git log of `prompts/job_parser/system.md`)
**Results:** `results/baseline/results.jsonl`
**Test set:** 12 jobs in `data/jobs_raw/`

### Observations from manual review

| Class of error                                                        | Count | Severity |
| --------------------------------------------------------------------- | ----- | -------- |
| Soft skills / responsibilities in `must_have`                         | 5/12  | High     |
| `or` interpreted as `and` (e.g., Stripe Ruby/Go/Java)                 | 1/12  | Medium   |
| Internal level titles missed (e.g., "SE 5" → senior, should be staff) | 1/12  | Medium   |
| Red flags missed: hype-language, low-cost-region-only                 | 3/12  | Medium   |
| Categories instead of techs in `stack` ("cloud-native tooling")       | 1/12  | Low      |
| Education ("CS degree") in `must_have_skills`                         | 1/12  | Low      |

### Decisions for v2

Address top class first: clean up `must_have_skills` to be tech-only.

---

## v2: must_have_skills tech-only — TBD
