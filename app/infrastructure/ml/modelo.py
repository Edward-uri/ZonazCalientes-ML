import mlflow
import pandas as pd
from mlflow.tracking import MlflowClient
from app.config import settings

class ModeloZonasMlflow:
    def __init__(self):
        self._modelo = None
        self.version: str | None = None

    def cargar(self) -> None:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        uri = f"models:/{settings.modelo_nombre}/{settings.modelo_stage}"
        self._modelo = mlflow.pyfunc.load_model(uri)
        self.version = self._resolver_version()

    def _resolver_version(self) -> str:
        # Si el stage configurado ya es un número de versión, úsalo tal cual.
        if settings.modelo_stage != "latest":
            return settings.modelo_stage
        # "latest" -> resolver la versión numérica máxima registrada en el registry.
        try:
            client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
            versiones = client.search_model_versions(f"name='{settings.modelo_nombre}'")
            if versiones:
                return str(max(int(v.version) for v in versiones))
        except Exception:
            pass
        return settings.modelo_stage

    def disponible(self) -> bool:
        return self._modelo is not None

    def zonas(self, municipio: int, dia_tipo: str, hora: int) -> list[dict]:
        df = pd.DataFrame([{"municipio": municipio, "dia_tipo": dia_tipo, "hora": hora}])
        return self._modelo.predict(df)[0]
