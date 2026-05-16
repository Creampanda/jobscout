from bs4 import BeautifulSoup
import httpx
from pydantic import BaseModel, Field

REMOTIVE_JOB_LINK = "https://remotive.com/api/remote-jobs"


class RemotiveJob(BaseModel):
    id: int | None = None
    title: str | None = None
    company_name: str | None = None
    category: str | None = None
    candidate_required_location: str | None = None
    salary: str | None = None
    url: str | None = None
    tags: list[str] = Field(default_factory=list)
    description_snippet: str


class RemotiveJobsResult(BaseModel):
    count: int
    jobs: list[RemotiveJob]


REMOTIVE_TOOL_DEF = {
    "name": "search_remote_jobs",
    "description": (
        "Returns recent remote jobs from Remotive (worldwide, English). "
        "Use when user is looking for fully-remote roles. "
        "There is no server side filtration. You can filter by "
        "[`title`, `company_name`, `candidate_required_location`, `tags`, `description_snippet`] by yourself. "
        "`description_snippet` is cut to 500 symbols. "
        "There is CDN cache ~24h, so there is no need to refresh vacancies on the same run. "
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": (
                    "Max jobs to return (default 50). Remotive usually has ~20-30 in cache "
                    "so requesting more is fine but won't increase the result"
                ),
                "default": 50,
            }
        },
        "required": [],
    },
}


def search_remote_jobs(limit: int = 50) -> RemotiveJobsResult:
    resp = httpx.get(REMOTIVE_JOB_LINK, timeout=10)
    resp.raise_for_status()

    data = resp.json()
    raw_jobs = data["jobs"]

    result_jobs = []
    for job in raw_jobs[:limit]:
        html = job["description"]
        text = (
            BeautifulSoup(html, "html.parser")
            .get_text(separator=" ", strip=True)
            .strip()
        )
        snippet = text[:500]

        result_jobs.append(
            RemotiveJob(
                id=job.get("id"),
                title=job.get("title"),
                company_name=job.get("company_name"),
                category=job.get("category"),
                candidate_required_location=job.get("candidate_required_location"),
                salary=job.get("salary"),
                url=job.get("url"),
                tags=job.get("tags") or [],
                description_snippet=snippet,
            )
        )

    return RemotiveJobsResult(count=len(result_jobs), jobs=result_jobs)
