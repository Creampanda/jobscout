from pydantic import BaseModel


class ToolError(BaseModel):
    error: str
