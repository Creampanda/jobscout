from pydantic import BaseModel


class ToolError(BaseModel):
    error: str


class ToolCallTrace(BaseModel):
    round_idx: int
    tool_use_id: str  # block.id от Anthropic, нужен для дедупа и связи с tool_result
    tool_name: str
    input: dict  # block.input — аргументы, которые модель передала
    output_size_bytes: int
    output_summary: str  # короткая человекочитаемая, типа "22 jobs returned" / "404
    latency_ms: int  # сколько секунд выполнялась тулза
    error: str | None  # None если успех, иначе текст ошибки
    timestamp: str  # ISO-8601 UTC, чтобы можно было сортировать
