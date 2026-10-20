from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://pulse:pulse@localhost:5432/pulse"
    secret_key: str = ""
    demo_data: bool = True
    admin_email: str = ""
    admin_password: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model_id: str = ""
    llm_allowed_model_ids: str = ""
    llm_input_rub_per_million: float = Field(default=0, ge=0)
    llm_output_rub_per_million: float = Field(default=0, ge=0)
    llm_daily_budget_rub: float = Field(default=500, gt=0, le=500)
    source_config: str = "data/sources.json"
    worker_poll_seconds: float = Field(default=1, gt=0)

    @model_validator(mode="after")
    def validate_model(self):
        if self.llm_base_url:
            if not self.llm_base_url.startswith("https://") or not self.llm_api_key:
                raise ValueError("LLM requires HTTPS and an API key")
            if self.llm_model_id not in self.llm_allowed_model_ids.split(","):
                raise ValueError("LLM_MODEL_ID must be in LLM_ALLOWED_MODEL_IDS")
            if min(self.llm_input_rub_per_million, self.llm_output_rub_per_million) <= 0:
                raise ValueError("Set provider token prices in RUB to enforce the team budget")
        return self
