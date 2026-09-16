from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="GREENLIGHT_", extra="ignore")

    database_url: str = "postgresql+psycopg://greenlight:greenlight@localhost:5433/greenlight"
    storage_dir: str = "./var/documents"
    cors_origins: str = "http://localhost:3100,http://localhost:3000,http://127.0.0.1:3000"
    # Optional extra origins as a regex, e.g. Lovable preview domains while testing a hosted frontend. Off by default.
    cors_origin_regex: str = ""
    max_upload_bytes: int = 25 * 1024 * 1024
    max_pages_per_document: int = 200

    # Claude. Credentials come from the SDK's usual sources (ANTHROPIC_API_KEY, or an `ant auth login` profile).
    llm_model: str = "claude-opus-5"
    llm_effort: str | None = None  # None = API default ("high")
    llm_max_tokens: int = 16000

    # Screens D and E defer to "established Distribution Provider practice", which PG&E does not publish.
    # When enabled, clearly labelled demonstration values are used; when disabled, D and E go to an engineer.
    synthetic_utility_practice: bool = True

    # Applicant notices. Without smtp_host they are recorded and shown in the portal, but not delivered.
    portal_base_url: str = "http://localhost:3100"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "interconnection@greenlight.example"
    smtp_starttls: bool = True

    agent_step_budget: int = 12  # model calls per review
    agent_cost_ceiling_usd: str = "1.00"


settings = Settings()
