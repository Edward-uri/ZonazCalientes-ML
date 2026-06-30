from datetime import datetime, timezone
from app.application.buckets import dia_tipo
from app.infrastructure.db.models import Inferencia

class PredecirZonasCalientes:
    def __init__(self, modelo, repo):
        self.modelo = modelo
        self.repo = repo

    def ejecutar(self, municipio: int, dia_semana: int, hora: int, top: int = 3) -> dict:
        dt = dia_tipo(dia_semana)
        # Las zonas ya vienen rankeadas por intensidad desc; se devuelven solo las top-N mas fuertes.
        zonas = self.modelo.zonas(municipio, dt, hora)[:top]
        salida = {
            "municipio": municipio,
            "bucket": {"dia_tipo": dt, "hora": hora},
            "zonas": zonas,
            "modelo_version": self.modelo.version,
            "generado_en": datetime.now(timezone.utc).isoformat(),
        }
        self.repo.guardar(Inferencia(
            municipio=municipio,
            input={"dia_semana": dia_semana, "hora": hora},
            output={"zonas": zonas},
            modelo_version=str(self.modelo.version),
        ))
        return salida
