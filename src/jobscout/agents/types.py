from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from jobscout.tools.extract_job import ExtractedJob


class ToolCallTrace(BaseModel):
    round_idx: int
    tool_use_id: str
    tool_name: str
    input: dict
    output_size_bytes: int
    output_summary: str
    latency_seconds: float
    is_error: bool
    timestamp: datetime


class AgentMetadata(BaseModel):
    model: str
    rounds_used: int
    stop_reason: str
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: Decimal
    system_prompt_hash: str
    timestamp: datetime


class AgentResult(BaseModel):
    metadata: AgentMetadata
    extracted_jobs: list[ExtractedJob]
    traces: list[ToolCallTrace]
    final_text: str | None
