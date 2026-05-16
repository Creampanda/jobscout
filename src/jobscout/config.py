from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    deepseek_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")

    llm_provider: str = Field(default="deepseek")
    llm_model: str = Field(default="deepseek-v4-flash")


    @property
    def project_root(self) -> Path:
        return Path(__file__).parent.parent.parent


settings = Settings()
