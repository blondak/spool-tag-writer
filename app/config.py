from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_host: str = "0.0.0.0"
    app_port: int = 8080

    spoolman_url: str = "http://localhost:7912"
    spoolman_api_key: str | None = None
    spoolman_api_header: str = "X-API-Key"

    local_nfc_enabled: bool = True
    nfc_backend: str = "pcsc"
    nfc_reader_name: str = "ACR122"
    ntag215_start_page: int = 4
    ntag215_end_page: int = 129
    mock_storage_file: str = "/tmp/spool-tag-writer.bin"
    request_timeout_seconds: float = 10.0

    moonraker_ws_url: str = "ws://127.0.0.1:7125/websocket"
    moonraker_http_url: str | None = None
    moonraker_api_key: str | None = None
    moonraker_client_name: str = "spool-tag-writer"
    moonraker_client_version: str = "0.1.0"
    moonraker_client_url: str = "https://local/spool-tag-writer"
    moonraker_agent_method: str = "spool_tag_writer.write_spool_tag"
    moonraker_remote_method: str = "spool_tag_writer_write_spool_tag"
    moonraker_show_mapping_agent_method: str = "spool_tag_writer.show_fallback_mapping"
    moonraker_show_mapping_remote_method: str = "spool_tag_writer_show_fallback_mapping"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
