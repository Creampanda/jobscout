from bs4 import BeautifulSoup
import httpx
from pydantic import BaseModel

ARBEITNOW_JOB_LINK = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowJob(BaseModel):
    slug: str
    company_name: str
    title: str
    location: str
    remote: bool
    url: str
    tags: list[str]
    job_types: list[str]
    created_at: int
    description_snippet: str


class ArbeitnowJobsResult(BaseModel):
    page: int
    count: int
    jobs: list[ArbeitnowJob]


ARBEITNOW_TOOL_DEF = {
    "name": "search_european_jobs",
    "description": (
        "Returns recent remote jobs from Arbeitnow (Germany, Europe). "
        "Use when user is looking for job in Europe. "
        "Listings come in both English and German. "
        "There are 100 jobs on one page."
        "You can filter by [`title`, `company_name`, `location`, `tags`, `description_snippet`] by yourself. "
        "`description_snippet` is cut to 500 symbols. "
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "page": {
                "type": "integer",
                "description": (
                    "Number of current page for pagination. "
                    "Search only on first page. No need for pagination"
                ),
                "default": 1,
            }
        },
        "required": [],
    },
}


def search_european_jobs(page: int = 1) -> dict:
    """
    Returns European jobs from Arbeitnow (mix of remote/onsite, English+German).
    """
    resp = httpx.get(ARBEITNOW_JOB_LINK, params={"page": page}, timeout=10)
    resp.raise_for_status()

    data = resp.json()

    raw_jobs = data["data"]

    result_jobs = []
    for job in raw_jobs:
        html = job["description"]
        text = (
            BeautifulSoup(html, "html.parser")
            .get_text(separator=" ", strip=True)
            .strip()
        )
        snippet = text[:500]

        result_jobs.append(
            ArbeitnowJob(
                slug=job.get("slug"),
                company_name=job.get("company_name"),
                title=job.get("title"),
                location=job.get("location"),
                remote=job.get("remote"),
                url=job.get("url"),
                tags=job.get("tags"),
                job_types=job.get("job_types"),
                created_at=job.get("created_at"),
                description_snippet=snippet,
            )
        )

    return ArbeitnowJobsResult(page=page, count=len(result_jobs), jobs=result_jobs)
