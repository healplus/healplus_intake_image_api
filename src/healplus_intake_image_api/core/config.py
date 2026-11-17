from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import urlsplit


class Settings(BaseSettings):
    database_url: str
    fhir_base_url: str = "http://127.0.0.1:8000/api/fhir/r4"
    api_client_tokens: dict[str, SecretStr] = Field(default_factory=dict)
    require_https: bool = False
    max_request_bytes: int = Field(default=32 * 1024 * 1024, ge=1024)
    analysis_timeout_seconds: int = Field(default=120, ge=1)
    analysis_max_attempts: int = Field(default=3, ge=1, le=20)
    analysis_retry_base_seconds: float = Field(default=2, gt=0)
    analysis_lease_seconds: int = Field(default=60, ge=1)
    worker_poll_seconds: float = Field(default=1, gt=0)

    @field_validator("fhir_base_url")
    @classmethod
    def validate_fhir_base_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("FHIR_BASE_URL deve ser uma URL HTTP absoluta sem credenciais, query ou fragmento")
        return value.rstrip("/")

    @field_validator("api_client_tokens")
    @classmethod
    def validate_tokens(cls, tokens: dict[str, SecretStr]) -> dict[str, SecretStr]:
        """Impede credenciais fracas ou ambíguas entre clientes."""
        values = [token.get_secret_value() for token in tokens.values()]
        if any(not client.strip() or len(client) > 128 or client.startswith("__legacy__") for client in tokens):
            raise ValueError("Identificador de cliente inválido")
        if any(len(value) < 32 for value in values) or len(set(values)) != len(values):
            raise ValueError("Tokens devem ser únicos e ter pelo menos 32 caracteres")
        return tokens

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
