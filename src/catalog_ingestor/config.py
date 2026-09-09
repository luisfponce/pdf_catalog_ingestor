from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://catalog:catalog@localhost:5432/catalog"
    output_dir: Path = Path("data/output")
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
