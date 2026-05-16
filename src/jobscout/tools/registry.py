import httpx
from pydantic import ValidationError

from jobscout.tools.remotive import REMOTIVE_TOOL_DEF, search_remote_jobs
from jobscout.tools.types import ToolError

TOOLS = {"search_remote_jobs": search_remote_jobs}

TOOL_DEFINITIONS = [
    REMOTIVE_TOOL_DEF
]


def execute_tool(name: str, arguments: dict) -> dict:
    if name not in TOOLS:
        return ToolError(error=f"Unknown tool: {name}").model_dump()
    try:
        result = TOOLS[name](**arguments)
        return result.model_dump()
    except (httpx.HTTPError, ValidationError, KeyError, ValueError) as e:
        return ToolError(error=str(e)).model_dump()
