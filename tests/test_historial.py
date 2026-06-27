from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine
from sqlalchemy.pool import StaticPool
import app.infrastructure.db.session as db

class ModeloFake:
    version = "test"
    def disponible(self): return True
    def zonas(self, municipio, dia_tipo, hora): return []

def _client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    db.engine = engine
    from app.main import app
    app.state.modelo = ModeloFake()
    return TestClient(app)

def test_historial_pagina_y_filtra():
    client = _client()
    for m in (1, 1, 2):
        client.post("/inferencias", json={"municipio": m, "dia_semana": 1, "hora": 8})
    assert len(client.get("/inferencias").json()) == 3
    assert len(client.get("/inferencias?municipio=1").json()) == 2
    assert len(client.get("/inferencias?limit=1").json()) == 1
