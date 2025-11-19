from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings"""

    APP_NAME: str = "Product Importer"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
