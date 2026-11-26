"""平台启动与存储配置。环境变量示例和完整取值见仓库根目录的 `.env.example`。"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID

from comfyshop_worker_protocol import DEFAULT_MAX_ARTIFACT_BYTES
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from comfyshop_api.core.languages import DEFAULT_LANGUAGE, LANGUAGES
from comfyshop_media.settings import MediaSettings, validate_http_url


class Settings(MediaSettings):
    """以 `COMFYSHOP_` 加字段名的大写形式读取配置，进程环境优先于 `.env`。"""

    model_config = SettingsConfigDict(
        env_prefix="COMFYSHOP_",
        env_file=".env",
        env_ignore_empty=True,
        env_nested_delimiter="__",
        extra="ignore",
        populate_by_name=True,
        hide_input_in_errors=True,
    )

    app_name: str = "ComfyShop API"
    debug: bool = False
    # 持久化数据与构建产物可以位于不同目录。Docker 将 /data 挂载为数据卷。
    data_dir: Path = Path.home() / ".local" / "share" / "comfyshop"
    database_url: str | None = None
    static_dir: Path | None = Path("dist")
    default_language: str = DEFAULT_LANGUAGE
    menu_languages: str | None = None
    cookie_secure: bool = False
    allowed_hosts: list[str] = ["*"]
    session_ttl_seconds: int = Field(default=604800, ge=60, le=2592000)
    # 任务心跳续期时从当前时间重新计算租约，单位秒。
    worker_lease_seconds: int = Field(default=90, ge=10, le=600)
    official_owner: str | None = None
    official_quote_url: str | None = None
    connection_encryption_key: SecretStr | None = None
    worker_service_tokens: dict[str, SecretStr] = Field(default_factory=dict)
    max_artifact_bytes: int = Field(default=DEFAULT_MAX_ARTIFACT_BYTES, ge=1024)
    # 一次执行最多回传的成品数。
    max_execution_artifacts: int = Field(default=256, ge=1, le=1024)
    failed_artifact_ttl_seconds: int = Field(default=86400, ge=60)
    max_asset_bytes: int = Field(default=256 * 1024 * 1024, ge=1024)
    asset_quota_bytes: int = Field(default=10 * 1024**3, ge=1024)
    team_asset_quota_bytes: dict[UUID, Annotated[int, Field(ge=1024)]] = Field(default_factory=dict)
    unused_asset_ttl_seconds: int = Field(default=86400, ge=60)
    # 额外允许的浏览器来源。`security.check_origin` 同时允许请求自身的来源。
    allowed_origins: list[str] = [
        "http://127.0.0.1:8688",
        "http://localhost:8688",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]

    # 邮件服务，用于找回密码。不填 `smtp_host` 时不发邮件，重置链接写入服务日志。
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str = "ComfyShop <no-reply@localhost>"
    # starttls 先明文连接再升级，ssl 直接加密连接，none 不加密。
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    # 对外的可信平台地址，用于邮件链接、工作机启动包和分享预览。邮件链接不回退到请求的
    # Host；启动包和分享预览在未配置时沿用请求地址。
    public_url: str | None = None
    web_push_enabled: bool = True
    web_push_contact: str | None = None
    password_reset_ttl_seconds: int = Field(default=1800, ge=60, le=86400)
    # 绑定邮箱的确认链接有效期。
    email_confirm_ttl_seconds: int = Field(default=86400, ge=60, le=604800)

    @field_validator("public_url", "official_quote_url")
    @classmethod
    def trusted_public_url(cls, value: str | None) -> str | None:
        return validate_http_url(value)

    @field_validator("web_push_contact")
    @classmethod
    def valid_web_push_contact(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value.startswith("mailto:") and "@" in value and not any(c.isspace() for c in value):
            return value
        if value.startswith("https://"):
            return validate_http_url(value)
        raise ValueError("Web Push 联系方式须为 HTTPS URL 或 mailto")

    @field_validator("default_language")
    @classmethod
    def supported_language(cls, value: str) -> str:
        language = value.strip()
        if language not in LANGUAGES:
            raise ValueError("默认语言必须是平台支持的语言")
        return language

    @model_validator(mode="after")
    def default_official_owner(self) -> Self:
        values = [value.get_secret_value() for value in self.worker_service_tokens.values()]
        if len(values) != len(set(values)) or any(len(value) < 32 for value in values):
            raise ValueError("各类服务工作机需要独立的至少 32 位令牌")
        if "official" in self.worker_service_tokens and self.official_owner is None:
            self.official_owner = "ComfyShop"
        return self

    def is_official_owner(self, username: str) -> bool:
        return username == self.official_owner

    def asset_quota_for(self, team_id: str | None) -> int:
        if team_id is None:
            return self.asset_quota_bytes
        return self.team_asset_quota_bytes.get(UUID(team_id), self.asset_quota_bytes)

    def platform_url(self, request_base_url: str) -> str:
        """返回写给浏览器以外的客户端的平台地址，未配置 `public_url` 时沿用请求地址。"""
        return self.public_url or request_base_url.rstrip("/")

    @property
    def database_dsn(self) -> str:
        """返回显式数据库连接地址，省略时在数据目录使用 SQLite。"""
        return self.database_url or f"sqlite:///{self.data_dir / 'comfyshop.db'}"


@lru_cache
def get_settings() -> Settings:
    """加载并共享进程内的配置。取值类型或范围无效时，Pydantic 抛出校验异常。"""
    return Settings()
