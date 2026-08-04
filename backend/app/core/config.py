from pydantic import model_validator
from pydantic_settings import BaseSettings

# Placeholder values shipped in the example env files. They must never reach a
# production process: a known jwt_secret lets anyone forge a token for any user.
INSECURE_PLACEHOLDERS = {"", "change_me", "change_me_to_a_long_random_secret"}
MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    # App database (stores users, datasources, settings, etc.)
    # Business data databases are configured per-datasource in the datasources table.
    app_name: str = "smart-bi"
    api_prefix: str = "/api"
    # "development" | "production". Production applies fail-closed secret checks
    # and disables the built-in demo account seeding.
    environment: str = "development"
    database_url: str = "postgresql+psycopg2://user:password@localhost:5432/smart_bi"
    cube_api_url: str = "http://localhost:4000/cubejs-api/v1"
    cube_api_token: str = "change_me"
    doris_enabled: bool = False
    doris_host: str = "doris-fe"
    doris_query_port: int = 9030
    doris_http_port: int = 8030
    doris_user: str = "root"
    doris_password: str = ""
    doris_database: str = "smart_bi_olap"
    doris_materialization_limit: int = 100000
    goview_enabled: bool = True
    goview_base_url: str = "http://localhost:3000"
    goview_embed_base_url: str | None = None
    goview_view_path: str = "/#/project/items"
    goview_design_path: str = "/#/project/items"
    goview_bridge_secret: str = ""
    llm_provider: str = "custom"
    llm_api_base: str = "http://localhost:8001/v1"
    llm_api_key: str = "change_me"
    llm_model: str = "gpt-4o-mini"
    llm_openai_base: str = "https://api.openai.com/v1"
    llm_openai_key: str = "change_me"
    llm_openai_model: str = "gpt-4o-mini"
    llm_moonshot_base: str = "https://api.moonshot.cn/v1"
    llm_moonshot_key: str = "change_me"
    llm_moonshot_model: str = "moonshot-v1-8k"
    llm_deepseek_base: str = "https://api.deepseek.com/v1"
    llm_deepseek_key: str = "change_me"
    llm_deepseek_model: str = "deepseek-chat"
    llm_dashscope_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_dashscope_key: str = "change_me"
    llm_dashscope_model: str = "qwen3.6-35b-a3b"
    llm_pi_base: str = "http://localhost:8001/v1"
    llm_pi_key: str = "change_me"
    llm_pi_model: str = "pi/pi-mono"
    llm_gemini_base: str = "https://generativelanguage.googleapis.com/v1beta"
    llm_gemini_key: str = "change_me"
    llm_gemini_model: str = "gemini-1.5-flash"
    llm_connect_timeout_seconds: float = 10.0
    llm_read_timeout_seconds: float = 120.0
    jwt_secret: str = "change_me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    # Comma-separated allowlist, e.g. "https://bi.example.com,https://app.example.com".
    # "*" is rejected in production.
    cors_origins: str = "*"
    # Seeds the built-in admin/demo accounts on startup. Forced off in production.
    seed_demo_accounts: bool = True
    # Directory for generated report export files. Relative paths resolve against backend/.
    report_export_dir: str = "exports"
    # Shared secret for internal service-to-service endpoints (/api/internal/*),
    # e.g. the agent Node service fetching the LLM config. Empty disables them.
    internal_api_secret: str = ""

    class Config:
        env_file = ".env"

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"production", "prod"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _enforce_production_hardening(self) -> "Settings":
        if not self.is_production:
            return self

        errors: list[str] = []
        if self.jwt_secret.strip() in INSECURE_PLACEHOLDERS:
            errors.append("JWT_SECRET is unset or still a placeholder value")
        elif len(self.jwt_secret.strip()) < MIN_SECRET_LENGTH:
            errors.append(f"JWT_SECRET must be at least {MIN_SECRET_LENGTH} characters")
        if "*" in self.cors_origin_list:
            errors.append("CORS_ORIGINS must be an explicit allowlist, not '*'")

        if errors:
            raise ValueError(
                "Refusing to start with ENVIRONMENT=production:\n  - "
                + "\n  - ".join(errors)
                + "\nGenerate a secret with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
            )
        # Demo accounts use publicly known passwords; never seed them in production.
        self.seed_demo_accounts = False
        return self


settings = Settings()
