from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "SAC Studio"
    database_path: str = "data/studio.db"
    public_base_url: str = "http://127.0.0.1:8000"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    default_openai_model: str = "gpt-6.1-sol"
    default_anthropic_model: str = "claude-sonnet-4-5"
    default_image_model: str = "gpt-image-2.6-flare"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
Path("data/assets").mkdir(parents=True, exist_ok=True)
Path("data/exports").mkdir(parents=True, exist_ok=True)
