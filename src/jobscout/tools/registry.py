import httpx
from pydantic import ValidationError

from jobscout.tools.arbeitnow import ARBEITNOW_TOOL_DEF, search_european_jobs
from jobscout.tools.remotive import REMOTIVE_TOOL_DEF, search_remote_jobs
from jobscout.tools.extract_job import EXTRACT_JOB_TOOL_DEF, extract_job_posting
from jobscout.tools.types import ToolError

TOOLS = {
    "search_remote_jobs": search_remote_jobs,
    "search_european_jobs": search_european_jobs,
    "extract_job_posting": extract_job_posting,
}

TOOL_DEFINITIONS = [REMOTIVE_TOOL_DEF, ARBEITNOW_TOOL_DEF, EXTRACT_JOB_TOOL_DEF]


def execute_tool(name: str, arguments: dict) -> dict:
    if name not in TOOLS:
        return ToolError(error=f"Unknown tool: {name}").model_dump()
    try:
        result = TOOLS[name](**arguments)
        return result.model_dump()
    except (httpx.HTTPError, ValidationError, KeyError, ValueError) as e:
        return ToolError(error=str(e)).model_dump()
