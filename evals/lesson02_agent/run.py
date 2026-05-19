import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from jobscout.agents.job_finder import run_job_finder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the lesson 2 job-finder agent.")
    parser.add_argument(
        "--skills",
        required=True,
        help="Comma-separated list of skills, e.g. --skills go,kafka,backend",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=8,
        help="Hard limit on tool-use rounds (default: 8).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    skills = [s.strip() for s in args.skills.split(",") if s.strip()]
    if not skills:
        raise SystemExit("No skills given. Use --skills go,kafka,backend.")

    run_name = os.environ.get("RUN_NAME") or datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    out_dir = Path("evals/lesson02_agent/results") / run_name
    out_dir.mkdir(parents=True, exist_ok=True)

    result = run_job_finder(skills, max_rounds=args.max_rounds, dump_dir=out_dir)

    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as f:
        for job in result.extracted_jobs:
            f.write(job.model_dump_json() + "\n")

    with (out_dir / "traces.jsonl").open("w", encoding="utf-8") as f:
        for trace in result.traces:
            f.write(trace.model_dump_json() + "\n")

    summary = result.metadata.model_dump(mode="json")
    summary.update(
        {
            "skills": skills,
            "jobs_extracted": len(result.extracted_jobs),
            "tool_calls_total": len(result.traces),
            "tool_calls_by_name": dict(
                Counter(t.tool_name for t in result.traces)
            ),
            "final_text": result.final_text,
        }
    )
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(
        f"run={run_name} rounds={result.metadata.rounds_used} "
        f"jobs={len(result.extracted_jobs)} "
        f"cost=${result.metadata.total_cost_usd}"
    )


if __name__ == "__main__":
    main()
