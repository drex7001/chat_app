from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    OPENAI_API_KEY: str = "sk-..."
    DATABASE_URL: str = "mysql+aiomysql://root:password@localhost/ai_db"
    CRM_API_URL: str = "http://crm.example.com"
    CRM_API_KEY: str = "crm-key"
    OPS_API_URL: str = "http://ops.example.com"
    OPS_API_KEY: str = "ops-key" # Still needed for generic OPS calls?
    
    ADMIN_API_URL: str = "http://admin.example.com"
    ADMIN_API_KEY: str = "admin-key"
    
    MILVUS_URI: str = "http://localhost:19530"
    MILVUS_TOKEN: str = "root:Milvus"
    
    # Zilliz Support (Users often use these names)
    ZILLIZ_API_URL: str = ""
    ZILLIZ_API_KEY: str = ""

    def model_post_init(self, __context):
        if self.ZILLIZ_API_URL:
            self.MILVUS_URI = self.ZILLIZ_API_URL
        if self.ZILLIZ_API_KEY:
            self.MILVUS_TOKEN = self.ZILLIZ_API_KEY

settings = Settings()
