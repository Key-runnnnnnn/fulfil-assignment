from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path

# Load .env file explicitly using python-dotenv
from dotenv import load_dotenv

# Get the backend directory path
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

# Load environment variables from .env file
load_dotenv(dotenv_path=ENV_FILE)


class Settings(BaseSettings):
    """
    Application configuration settings.
    All settings are loaded from environment variables or .env file.
    """

    # App Settings
    APP_NAME: str = "Product Importer"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Database Configuration - PostgreSQL
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"
    DB_NAME: str = "product_importer"

    # Optional: Override with full DATABASE_URL if provided
    DATABASE_URL: Optional[str] = None

    @property
    def get_database_url(self) -> str:
        """Construct database URL from components or use provided URL"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env


# Initialize settings (will automatically load from .env)
settings = Settings()

# Log which .env file is being used (only in debug mode)
if settings.DEBUG:
    import logging
    logger = logging.getLogger(__name__)
    if ENV_FILE.exists():
        logger.info(f"Loaded environment variables from: {ENV_FILE}")
    else:
        logger.warning(
            f".env file not found at: {ENV_FILE}. Using default values.")
