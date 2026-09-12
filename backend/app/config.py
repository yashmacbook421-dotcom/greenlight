from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="GREENLIGHT_", extra="ignore")

    database_url: str = "postgresql+psycopg://greenlight:greenlight@localhost:5433/greenlight"
    storage_dir: str = "./var/documents"
    max_upload_bytes: int = 25 * 1024 * 1024
    max_pages_per_document: int = 200


settings = Settings()
