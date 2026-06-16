import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determinar el directorio raíz del proyecto (donde reside el archivo .env)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    DATABASE_URL: str
    POSTGRES_SCHEMA: str = "sipp"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    BACKEND_URL: str = "http://localhost:8000"
    CSV_UPLOAD_DIR: str = "./data/uploads"
    TIMEZONE: str = "America/Lima"

settings = Settings()
