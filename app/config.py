from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação lidas de variáveis de ambiente.

    Pydantic-settings lê automaticamente do ambiente ou de um arquivo .env.
    Se a variável não existir, usa o valor padrão definido aqui.
    """

    model_config = SettingsConfigDict(env_file=".env")

    redis_host: str = "localhost"
    redis_port: int = 6379
    cache_ttl_seconds: int = 60

    # Rate Limiting
    rate_limit_requests: int = 10
    rate_limit_window: int = 60


settings = Settings()
