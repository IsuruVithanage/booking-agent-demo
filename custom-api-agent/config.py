from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_port: int = Field(default=8085, validation_alias="APP_PORT")
    hotel_name: str = Field(default="Lakeside Grand Hotel", validation_alias="HOTEL_NAME")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")
    policy_file_path: str = Field(
        default="/etc/config/cancellation-policy.txt",
        validation_alias="POLICY_FILE_PATH",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
