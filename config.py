from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    max_concurrent_requests: int = 10
    max_pages: int = 50
    request_timeout: int = 10

    class Config:
        env_file = ".env"

settings = Settings()