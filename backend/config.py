from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Real environment variables win over .env (used in Docker/AWS later)
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str


settings = Settings()
