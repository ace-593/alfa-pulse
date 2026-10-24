from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ORGANIZER_LLM_URL = "https://changellenge.up.railway.app/v1"
DEFAULT_LLM_MODEL = "auto"
ROUTING_MODELS = {
    "planning": "google/gemma-4-26b-a4b-it",
    "answer": "qwen/qwen3.6-35b-a3b",
    "reasoning": "z-ai/glm-5.3-flash",
    "research": "deepseek/deepseek-v4.1-flash",
}
ALLOWED_LLM_MODELS = {
    "google/gemma-4-26b-a4b-it": "Gemma 4 26B A4B",
    "z-ai/glm-5.3-flash": "GLM-5.3-Flash",
    "qwen/qwen3.6-35b-a3b": "Qwen3.6 35B A3B",
    "deepseek/deepseek-v4.1-flash": "DeepSeek-V4.1-Flash",
    "qwen/qwen3-vl-30b-a3b-instruct": "Qwen3-VL-30B-A3B-Instruct",
    "moonshotai/kimi-k2.6": "Kimi-K2.6",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)
    database_url: str = "postgresql+asyncpg://pulse:pulse@localhost:5432/pulse"
    secret_key: str = ""
    demo_data: bool = True
    admin_email: str = ""
    admin_password: str = ""
    llm_base_url: str = ""
    llm_api_key: str = Field(default="", repr=False, exclude=True)
    alfa_api_key: str = Field(default="", repr=False, exclude=True)
    llm_model_id: str = DEFAULT_LLM_MODEL
    llm_model_family: str = ""
    llm_allowed_model_ids: str = ""
    llm_input_rub_per_million: float = Field(default=0, ge=0)
    llm_output_rub_per_million: float = Field(default=0, ge=0)
    llm_daily_budget_rub: float = Field(default=500, gt=0, le=500)
    llm_daily_call_limit: int = Field(default=100, gt=0)
    llm_daily_token_limit: int = Field(default=250000, gt=0)
    llm_json_mode: bool = False
    source_config: str = "data/sources.json"
    worker_poll_seconds: float = Field(default=1, gt=0)

    @model_validator(mode="after")
    def validate_model(self):
        self.llm_api_key = self.llm_api_key.strip() or self.alfa_api_key.strip()
        self.llm_model_id = self.llm_model_id.strip() or DEFAULT_LLM_MODEL
        self.llm_base_url = self.llm_base_url.strip().rstrip("/")
        if self.llm_api_key and not self.llm_base_url:
            self.llm_base_url = ORGANIZER_LLM_URL
        if self.llm_base_url:
            if not self.llm_base_url.startswith("https://") or not self.llm_api_key:
                raise ValueError("LLM requires HTTPS and an API key")
            allowed = {value.strip() for value in self.llm_allowed_model_ids.split(",") if value.strip()}
            if self.llm_base_url == ORGANIZER_LLM_URL:
                if self.llm_model_id != "auto" and self.llm_model_id not in ALLOWED_LLM_MODELS:
                    raise ValueError("Choose an organizer-approved LLM_MODEL_ID; see backend/.env.example")
                self.llm_model_family = ALLOWED_LLM_MODELS.get(self.llm_model_id, "Automatic routing")
            elif not allowed:
                raise ValueError("Custom providers require LLM_ALLOWED_MODEL_IDS")
            if self.llm_model_id == "auto":
                if self.llm_base_url != ORGANIZER_LLM_URL:
                    raise ValueError("Custom providers require an explicit LLM_MODEL_ID")
                if allowed and not set(ROUTING_MODELS.values()) <= allowed:
                    raise ValueError("Automatic routing requires all routing models in LLM_ALLOWED_MODEL_IDS")
                if self.llm_input_rub_per_million or self.llm_output_rub_per_million:
                    raise ValueError("Per-model token prices require an explicit LLM_MODEL_ID")
            elif allowed and self.llm_model_id not in allowed:
                raise ValueError("LLM_MODEL_ID must be in LLM_ALLOWED_MODEL_IDS")
            prices = (self.llm_input_rub_per_million, self.llm_output_rub_per_million)
            if (any(prices) or self.llm_base_url != ORGANIZER_LLM_URL) and min(prices) <= 0:
                raise ValueError("Set provider token prices in RUB to enforce the team budget")
        return self
