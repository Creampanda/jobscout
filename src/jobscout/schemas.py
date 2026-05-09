from typing import Literal
from pydantic import BaseModel, Field, model_validator


class SalaryRange(BaseModel):
    min: int = Field(
        ge=0, description="Minimum salary in the specified currency and period"
    )
    max: int = Field(
        ge=0, description="Maximum salary in the specified currency and period"
    )
    currency: str = Field(
        description="Currency code as stated in the posting (e.g., 'USD', 'EUR', 'RUB')"
    )
    period: Literal["hour", "month", "year"] = Field(
        description="Period that min/max refer to: hourly, monthly, or yearly"
    )

    @model_validator(mode="after")
    def check_min_le_max(self) -> "SalaryRange":
        if self.min > self.max:
            raise ValueError(
                f"salary_range.min ({self.min}) must be <= salary_range.max ({self.max})"
            )
        return self


class JobPosting(BaseModel):
    role: str = Field(
        description="Position title verbatim from the posting, without normalization"
    )
    level: Literal["junior", "mid", "senior", "staff", "lead"] = Field(
        description="Seniority level inferred from the posting text"
    )
    stack: list[str] = Field(
        description="All technologies mentioned in the requirements (languages, frameworks, tools, databases)"
    )
    must_have_skills: list[str] = Field(
        description="Skills explicitly marked as required ('required', 'must have', 'mandatory')"
    )
    nice_to_have_skills: list[str] = Field(
        description="Skills marked as desirable ('plus', 'nice to have', 'preferred'). Must not overlap with must_have_skills"
    )
    salary_range: SalaryRange | None = Field(
        description="Salary range with min, max, currency, and period. None if not stated in the posting"
    )
    location: str | None = Field(
        description="Location verbatim from the posting, without normalization. None if not stated"
    )
    remote: Literal["onsite", "hybrid", "remote", "unspecified"] = Field(
        description="Work format: onsite, hybrid, fully remote, or unspecified"
    )
    company_summary: str | None = Field(
        default=None,
        description="Brief 1-2 sentence company description for context when drafting an application. None if the posting provides no information about the company",
    )
    red_flags: list[str] = Field(
        default_factory=list,
        description=(
            "Suspicious signals found in the posting. Examples: requiring many years of "
            "experience in a young technology, missing salary at a non-public company, "
            "excessively broad responsibilities for a single role, contradictions in requirements. "
            "Empty list if no red flags are detected"
        ),
    )
