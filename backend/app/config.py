from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings"""

    # App Settings
    APP_NAME: str = "Product Importer"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    
    # Database Configuration
    DATABASE_URL: str = "sqlite:///./product_importer.db"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
