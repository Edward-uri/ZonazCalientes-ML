from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./zonas.db"
    mlflow_tracking_uri: str = "./mlruns"
    modelo_nombre: str = "zonas-calientes"
    modelo_stage: str = "latest"

settings = Settings()
