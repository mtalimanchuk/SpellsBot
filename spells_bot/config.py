from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseModel):
    sqlalchemy_url: str
    drop: bool = False


class StorageSettings(BaseModel):
    data_root_dir: Path
    image_storage_url_root: str
    settings_icon_url: str
    warning_icon_url: str


class TelegramSettings(BaseModel):
    bot_token: str


class ApiSettings(BaseModel):
    base_web_url: str
    base_api_url: str
    spell_list_url: str
    class_list_url: str
    prestige_class_list_url: str
    spell_info_url_prefix: str


class HtmlToImageSettings(BaseModel):
    css_file: Path


class BotSettings(BaseSettings):
    # db
    db: DatabaseSettings
    # assets
    storage: StorageSettings
    # telegram
    telegram: TelegramSettings
    # spell data source
    api: ApiSettings
    # html to image
    hti: HtmlToImageSettings

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"


settings = BotSettings()
