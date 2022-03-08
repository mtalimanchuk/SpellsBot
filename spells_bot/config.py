from pathlib import Path

from pydantic import BaseSettings, BaseModel


class DatabaseSettings(BaseModel):
    sqlalchemy_url: str


class StorageSettings(BaseModel):
    data_root_dir: Path
    image_storage_url_root: str
    settings_icon_url: str


class TelegramSettings(BaseModel):
    bot_token: str


class DataSourceSettings(BaseModel):
    spell_list_url: str
    class_list_url: str
    prestige_class_list_url: str
    spell_info_url_prefix: str


class HctiSettings(BaseModel):
    url: str
    user_id: str
    api_key: str
    css_file: Path


class BotSettings(BaseSettings):
    # db
    db: DatabaseSettings
    # assets
    storage: StorageSettings
    # telegram
    telegram: TelegramSettings
    # spell data source
    source: DataSourceSettings
    # html to image
    hcti: HctiSettings

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
