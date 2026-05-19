import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from jobscout.agents.types import AgentMetadata, AgentResult, ToolCallTrace
from jobscout.llm import call_llm
from jobscout.pricing import calculate_cost
from jobscout.prompts import load_prompt, prompt_hash
from jobscout.tools.extract_job import ExtractedJob
from jobscout.tools.registry import TOOL_DEFINITIONS, execute_tool

SYSTEM_PROMPT = load_prompt("job_finder/system.md")
SYSTEM_PROMPT_HASH = prompt_hash(SYSTEM_PROMPT)

SEARCH_DUMP_NAMES = {
    "search_remote_jobs": "remotive_raw",
    "search_european_jobs": "arbeitnow_raw",
}


def run_job_finder(
    skills: list[str],
    max_rounds: int = 8,
    verbose: bool = True,
    dump_dir: Path | None = None,
) -> AgentResult:
    timestamp_start = datetime.now(timezone.utc)

    messages: list[dict] = [
        {
            "role": "user",
            "content": f"Find relevant remote jobs for skills: {', '.join(skills)}",
        }
    ]

    def log(msg: str) -> None:
        if verbose:
            print(msg, flush=True)

    log(f"agent start — skills={skills}, max_rounds={max_rounds}")

    traces: list[ToolCallTrace] = []
    extracted: list[ExtractedJob] = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = Decimal(0)
    final_text: str | None = None
    stop_reason = "max_rounds"
    rounds_used = max_rounds
    model_name = ""

    for round_idx in range(max_rounds):
        round_timestamp = datetime.now(timezone.utc)
        log(f"[round {round_idx + 1}/{max_rounds}] calling LLM...")
        llm_t0 = time.perf_counter()
        response = call_llm(
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice={"type": "auto"},
            max_tokens=4096,
        )
        llm_latency = time.perf_counter() - llm_t0

        if not model_name:
            model_name = response.model

        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens
        round_cost = calculate_cost(response.model, response.usage)
        total_cost += round_cost
        log(
            f"[round {round_idx + 1}/{max_rounds}] LLM stop={response.stop_reason} "
            f"in={response.usage.input_tokens} out={response.usage.output_tokens} "
            f"cost=${round_cost} ({llm_latency:.1f}s)"
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text":
                    final_text = block.text
                    break
            stop_reason = "end_turn"
            rounds_used = round_idx + 1
            log(f"[round {round_idx + 1}/{max_rounds}] end_turn — agent done")
            break

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            log(
                f"[round {round_idx + 1}/{max_rounds}] "
                f"executing {len(tool_use_blocks)} tool call(s)"
            )

            tool_results: list[dict] = []
            for tool_idx, block in enumerate(tool_use_blocks, start=1):
                tool_t0 = time.perf_counter()
                result = execute_tool(block.name, block.input)
                tool_latency = time.perf_counter() - tool_t0

                is_error = "error" in result
                result_json = json.dumps(result)
                summary = _summarize(block.name, result)

                marker = "FAIL" if is_error else "ok"
                log(
                    f"    [{tool_idx}/{len(tool_use_blocks)}] {block.name} "
                    f"-> {marker}: {summary} ({tool_latency:.1f}s)"
                )

                traces.append(
                    ToolCallTrace(
                        round_idx=round_idx,
                        tool_use_id=block.id,
                        tool_name=block.name,
                        input=block.input,
                        output_size_bytes=len(result_json),
                        output_summary=summary,
                        latency_seconds=tool_latency,
                        is_error=is_error,
                        timestamp=round_timestamp,
                    )
                )

                if block.name == "extract_job_posting" and not is_error:
                    extracted.append(ExtractedJob(**result))

                if (
                    dump_dir is not None
                    and not is_error
                    and block.name in SEARCH_DUMP_NAMES
                ):
                    base = SEARCH_DUMP_NAMES[block.name]
                    path = dump_dir / f"{base}.json"
                    if path.exists():
                        path = dump_dir / f"{base}_r{round_idx}.json"
                    path.write_text(
                        json.dumps(result, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    log(f"        dumped {block.name} -> {path.name}")

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_json,
                        "is_error": is_error,
                    }
                )

            messages.append({"role": "user", "content": tool_results})
            continue

        stop_reason = response.stop_reason or "unknown"
        rounds_used = round_idx + 1
        log(
            f"[round {round_idx + 1}/{max_rounds}] unexpected stop_reason={stop_reason}"
            " — aborting"
        )
        break
    else:
        log(f"hit max_rounds={max_rounds} without end_turn")

    log(
        f"agent done — rounds={rounds_used} stop={stop_reason} "
        f"jobs_extracted={len(extracted)} tool_calls={len(traces)} "
        f"total_cost=${total_cost}"
    )

    metadata = AgentMetadata(
        model=model_name,
        rounds_used=rounds_used,
        stop_reason=stop_reason,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_cost_usd=total_cost,
        system_prompt_hash=SYSTEM_PROMPT_HASH,
        timestamp=timestamp_start,
    )

    return AgentResult(
        metadata=metadata,
        extracted_jobs=extracted,
        traces=traces,
        final_text=final_text,
    )


def _summarize(tool_name: str, result: dict) -> str:
    """Short human-readable summary of a tool result for the trace log."""
    if "error" in result:
        return f"error: {result['error'][:120]}"
    if tool_name in ("search_remote_jobs", "search_european_jobs"):
        return f"{result.get('count', 0)} jobs"
    if tool_name == "extract_job_posting":
        posting = result.get("posting") or {}
        return f"extracted: {posting.get('title', '<no title>')}"
    return f"{len(json.dumps(result))} bytes"
