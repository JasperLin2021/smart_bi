from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App database (stores users, datasources, settings, etc.)
    # Business data databases are configured per-datasource in the datasources table.
    app_name: str = "smart-bi"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg2://user:password@localhost:5432/smart_bi"
    cube_api_url: str = "http://localhost:4000/cubejs-api/v1"
    cube_api_token: str = "change_me"
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
    llm_gemini_base: str = "https://generativelanguage.googleapis.com/v1beta"
    llm_gemini_key: str = "change_me"
    llm_gemini_model: str = "gemini-1.5-flash"
    jwt_secret: str = "change_me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    class Config:
        env_file = ".env"


settings = Settings()
