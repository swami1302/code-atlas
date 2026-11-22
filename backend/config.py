from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Real environment variables win over .env (used in Docker/AWS later)
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    redis_url: str
    # DEBUG, INFO, WARNING, ERROR; optional, defaults to INFO
    log_level: str = "INFO"
    # Google AI Studio key for the Gemini embedding API
    gemini_api_key: str


settings = Settings()
