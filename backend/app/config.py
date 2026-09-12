from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="GREENLIGHT_", extra="ignore")

    database_url: str = "postgresql+psycopg://greenlight:greenlight@localhost:5433/greenlight"
    storage_dir: str = "./var/documents"
    max_upload_bytes: int = 25 * 1024 * 1024
    max_pages_per_document: int = 200

    # Claude. Credentials come from the SDK's usual sources (ANTHROPIC_API_KEY, or an `ant auth login` profile).
    llm_model: str = "claude-opus-5"
    llm_effort: str | None = None  # None = API default ("high")
    llm_max_tokens: int = 16000

    # Screens D and E defer to "established Distribution Provider practice", which PG&E does not publish.
    # When enabled, clearly labelled demonstration values are used; when disabled, D and E go to an engineer.
    synthetic_utility_practice: bool = True


settings = Settings()
