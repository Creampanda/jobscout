import json
import time
from datetime import datetime, timezone
from pathlib import Path

from jobscout.config import settings
from jobscout.llm import call_llm
from jobscout.parsers.types import ParseMetadata, ParseResult
from jobscout.pricing import calculate_cost
from jobscout.prompts import load_prompt, prompt_hash
from jobscout.schemas import JobPosting

SYSTEM_PROMPT = load_prompt("job_parser/system.md")

TRACES_DIR = settings.project_root / "traces" / "lesson01"
TRACES_DIR.mkdir(parents=True, exist_ok=True)


def parse_job(job_text: str) -> ParseResult:
    tool = {
        "name": "extract_job_posting",
        "description": (
            "Extract structured data from a job posting: role, level, stack, "
            "salary range, location, work format, must-have and nice-to-have "
            "skills, red flags. If a field is not clearly stated, return null "
            "or an empty list — never invent values."
        ),
        "input_schema": JobPosting.model_json_schema(),
    }

    user_message = {
        "role": "user",
        "content": (
            "Extract structured data from the job posting below using the "
            "extract_job_posting tool.\n\n"
            f"<job_description>\n{job_text}\n</job_description>"
        ),
    }

    timestamp = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    response = call_llm(
        system=SYSTEM_PROMPT,
        messages=[user_message],
        tools=[tool],
        tool_choice={"type": "tool", "name": "extract_job_posting"},
        max_tokens=1500,
        temperature=0.0,
    )
    latency = time.perf_counter() - t0

    tool_use_block = next(
        (
            b
            for b in response.content
            if b.type == "tool_use" and b.name == "extract_job_posting"
        ),
        None,
    )
    if tool_use_block is None:
        raise RuntimeError(
            f"Model did not produce expected tool call. "
            f"stop_reason={response.stop_reason}, content={response.content}"
        )

    cost = calculate_cost(response.model, response.usage)

    filename = timestamp.strftime("%Y%m%dT%H%M%S_%f") + ".json"
    trace_path = TRACES_DIR / filename

    metadata = ParseMetadata(
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cost_usd=cost,
        latency_seconds=latency,
        trace_path=trace_path,
        system_prompt_hash=prompt_hash(SYSTEM_PROMPT),
        stop_reason=response.stop_reason,
        timestamp=timestamp,
    )

    # Пишем трейс ДО валидации — чтобы при ValidationError данные остались на диске
    _save_trace(
        job_text=job_text,
        parse_meta=metadata,
        parsed_input=tool_use_block.input,
        trace_path=trace_path,
    )

    parsed = JobPosting(**tool_use_block.input)

    return ParseResult(metadata=metadata, parsed=parsed)


def _save_trace(
    *,
    job_text: str,
    parse_meta: ParseMetadata,
    parsed_input: dict,
    trace_path: Path,
) -> None:
    """Сохраняет полный контекст вызова в JSON для последующего анализа."""
    trace = parse_meta.model_dump(mode="json")
    trace["job_text"] = job_text
    trace["parsed"] = parsed_input
    trace_path.write_text(
        json.dumps(trace, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
