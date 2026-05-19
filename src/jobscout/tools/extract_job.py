from pydantic import BaseModel
from jobscout.parsers.job_parser import parse_job
from jobscout.schemas import JobPosting


class ExtractedJob(BaseModel):
    source_url: str
    posting: JobPosting


EXTRACT_JOB_TOOL_DEF = {
    "name": "extract_job_posting",
    "description": (
        "Parse a job posting into a structured JobPosting (role, level, stack, "
        "salary, location, work format, must-have/nice-to-have skills, red flags). "
        "EXPENSIVE — calls an LLM internally. Use only on a pre-filtered shortlist "
        "of 3-7 jobs after you've decided they're relevant. Do NOT call on every "
        "search result."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "job_text": {
                "type": "string",
                "description": (
                    "Full text of the posting — concat title, company, location, "
                    "salary, tags, and description_snippet from the search result."
                ),
            },
            "source_url": {
                "type": "string",
                "description": "URL of the posting from the search result.",
            },
        },
        "required": ["job_text", "source_url"],
    },
}


def extract_job_posting(job_text: str, source_url: str) -> ExtractedJob:
    result = parse_job(job_text)
    return ExtractedJob(source_url=source_url, posting=result.parsed)
