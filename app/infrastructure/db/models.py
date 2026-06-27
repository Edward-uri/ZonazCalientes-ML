from datetime import datetime, timezone
from typing import Any
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON

class Inferencia(SQLModel, table=True):
    __tablename__ = "inferencias"
    id: int | None = Field(default=None, primary_key=True)
    municipio: int = Field(index=True)
    input: dict[str, Any] = Field(sa_column=Column(JSON))
    output: dict[str, Any] = Field(sa_column=Column(JSON))
    modelo_version: str
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
