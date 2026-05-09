from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from jobscout.schemas import JobPosting


class ParseMetadata(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    latency_seconds: float
    trace_path: Path | None
    system_prompt_hash: str
    stop_reason: str | None
    timestamp: datetime


class ParseResult(BaseModel):
    metadata: ParseMetadata
    parsed: JobPosting
