from pydantic import BaseSettings


class Settings(BaseSettings):
    SQLITEDB_PATH: str = "filmswap.db"
    SQL_ECHO: bool = False
    GUILD_ID: int = -1
    ALLOWED_ROLES: list[str] = []

    class Config:
        case_sensitive = False
        env_file = ".env"


settings = Settings()
