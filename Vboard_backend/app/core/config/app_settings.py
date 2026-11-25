from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Application-level settings."""

    # Application settings
    APP_NAME: str = "Vboard Backend"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
