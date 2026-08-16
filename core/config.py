import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    bot_token: str
    db_url: str
    admin_ids: str

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    @property
    def admin_ids_list(self) -> List[int]:
        if not self.admin_ids:
            return []
        return [int(x.strip()) for x in self.admin_ids.split(",") if x.strip().isdigit()]

try:
    config = Settings()
except Exception as e:
    # Fallback to os.environ if .env is missing or invalid
    config = Settings(
        bot_token=os.getenv("BOT_TOKEN", ""),
        db_url=os.getenv("DB_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/avtojavob"),
        admin_ids=os.getenv("ADMIN_IDS", "")
    )
