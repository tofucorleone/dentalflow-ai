from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_timezone: str = "Africa/Algiers"
    database_url: str
    jwt_secret: str = "development-only-change-me"

    google_calendar_enabled: bool = False
    google_service_account_file: str = "/run/secrets/google-service-account.json"

    openai_api_key: str | None = None

    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None

    twilio_recording_download_timeout: float = 15.0
    twilio_recording_download_attempts: int = 4


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
