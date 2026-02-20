from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    kiwi_api_key_search: str = ""
    kiwi_api_key_multi: str = ""
    google_maps_api_key: str = ""
    amadeus_api_key: str = ""
    amadeus_api_secret: str = ""
    port: int = 8000
    env: str = "development"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
