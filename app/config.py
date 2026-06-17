from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    discord_token: str = ""
    database_url: str = "sqlite+aiosqlite:///./data/discord_parser.db"
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_file = ".env"


settings = Settings()
