from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class InferenciaRequest(BaseModel):
    municipio: int
    dia_semana: int = Field(ge=0, le=6)
    hora: int = Field(ge=0, le=23)
    top: int = Field(default=3, ge=1, le=20, description="Maximo de zonas a devolver (las mas fuertes por intensidad)")

class ZonaOut(BaseModel):
    lat: float
    lng: float
    intensidad: float
    demand_density: float
    supply_demand_ratio: float
    n_requests: int
    n_celdas: int
    radio_m: float

class BucketOut(BaseModel):
    dia_tipo: str
    hora: int

class InferenciaResponse(BaseModel):
    municipio: int
    bucket: BucketOut
    zonas: list[ZonaOut]
    modelo_version: str
    generado_en: str

class InferenciaHistorialOut(BaseModel):
    """Forma de salida del historial (GET /inferencias), documentada en Swagger."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    municipio: int
    input: dict
    output: dict
    modelo_version: str
    creado_en: datetime
