from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    OPENAI_API_KEY: str = "sk-..."
    DATABASE_URL: str = "mysql+aiomysql://root:password@localhost/ai_db"
    CRM_API_URL: str = "http://crm.example.com"
    CRM_API_KEY: str = "crm-key"
    OPS_API_URL: str = "http://ops.example.com"
    OPS_API_KEY: str = "ops-key"

settings = Settings()
