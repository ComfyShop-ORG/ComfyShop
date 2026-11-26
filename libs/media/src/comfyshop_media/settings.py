"""媒体模块的配置，宿主可用环境变量或程序参数构造。"""

from functools import cached_property
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from comfyshop_media.storage import MediaStorage


def validate_http_url(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("地址必须是无内嵌凭据、查询参数和片段的 HTTP(S) 地址")
    return value


class MediaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COMFYSHOP_MEDIA_", hide_input_in_errors=True)

    data_dir: Path
    storage_backend: Literal["local", "s3"] = "local"
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_region: str = "us-east-1"
    s3_addressing_style: Literal["auto", "path", "virtual"] = "auto"
    s3_access_key_id: str | None = None
    s3_secret_access_key: SecretStr | None = None
    ffprobe: str = "ffprobe"
    ffmpeg: str = "ffmpeg"
    derivative_cache_max_bytes: int = Field(default=512 * 1024**2, ge=0)
    derivative_cache_ttl_seconds: int = Field(default=7 * 24 * 60 * 60, ge=1)

    @field_validator("s3_endpoint_url")
    @classmethod
    def endpoint(cls, value: str | None) -> str | None:
        return validate_http_url(value)

    @model_validator(mode="after")
    def validate_storage(self) -> Self:
        if self.storage_backend == "s3":
            if not self.s3_bucket or not self.s3_bucket.strip():
                raise ValueError("S3 存储需要配置存储桶")
            if bool(self.s3_access_key_id) != bool(self.s3_secret_access_key):
                raise ValueError("S3 访问密钥须同时配置，或一并省略以使用 SDK 凭据链")
        return self

    @cached_property
    def media_storage(self) -> MediaStorage:
        return MediaStorage(self)

    @property
    def original_dir(self) -> Path:
        return self.data_dir / "originals"

    @property
    def thumbnail_dir(self) -> Path:
        return self.data_dir / "thumbnails"

    @property
    def video_preview_dir(self) -> Path:
        return self.data_dir / "video-previews"
