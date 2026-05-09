import json
import time
from decimal import Decimal
from pathlib import Path

from jobscout.parsers.job_parser import parse_job

JOBS_DIR = Path("data/jobs_raw")
RESULTS_PATH = Path("evals/lesson01_parser/results.jsonl")
from datetime import datetime, timezone

run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
RESULTS_DIR = Path("evals/lesson01_parser/results") / run_timestamp
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_PATH = RESULTS_DIR / "results.jsonl"


def main() -> None:
    files = sorted(JOBS_DIR.glob("*.txt"))
    total = len(files)
    if total == 0:
        print(f"No .txt files found in {JOBS_DIR}")
        return

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    for i, file in enumerate(files, 1):
        record: dict = {"job_file": file.name}
        cost = Decimal(0)
        status = "?"

        t0 = time.perf_counter()
        try:
            parse_result = parse_job(file.read_text(encoding="utf-8"))
        except Exception as e:
            status = "error"
            record["status"] = status
            record["error_type"] = type(e).__name__
            record["error_message"] = repr(e)
            record["trace_file"] = None
        else:
            status = "ok"
            record["status"] = status
            record["parsed"] = parse_result.parsed.model_dump(mode="json")
            record["trace_file"] = str(parse_result.metadata.trace_path)
            cost = parse_result.metadata.cost_usd
            record["cost_usd"] = str(cost)
        finally:
            elapsed = time.perf_counter() - t0
            record["elapsed_seconds"] = round(elapsed, 3)

        print(f"[{i}/{total}] {status:5s} {file.name:50s} ${cost:.4f}  {elapsed:4.1f}s")
        results.append(record)

    with RESULTS_PATH.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    ok_count = sum(r["status"] == "ok" for r in results)
    total_cost = sum(Decimal(r["cost_usd"]) for r in results if r["status"] == "ok")
    print(
        f"\nDone. {ok_count}/{total} ok. "
        f"Total cost: ${total_cost:.4f}. "
        f"Results: {RESULTS_PATH}"
    )


if __name__ == "__main__":
    main()
