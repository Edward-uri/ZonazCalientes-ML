from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine
from sqlalchemy.pool import StaticPool
import app.infrastructure.db.session as db

# Modelo falso: una zona fija para (1, entre_semana, 18), vacío para el resto.
class ModeloFake:
    version = "test"
    def disponible(self): return True
    def zonas(self, municipio, dia_tipo, hora):
        if (municipio, dia_tipo, hora) == (1, "entre_semana", 18):
            return [{
                "lat": 16.752, "lng": -93.116, "intensidad": 1.0,
                "demand_density": 432.1, "supply_demand_ratio": 0.18,
                "n_requests": 176, "n_celdas": 4, "radio_m": 380.0,
            }]
        return []

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

def test_inferencia_devuelve_zonas_y_guarda():
    client = _client()
    r = client.post("/inferencias", json={"municipio": 1, "dia_semana": 3, "hora": 18})
    assert r.status_code == 200
    body = r.json()
    assert body["bucket"] == {"dia_tipo": "entre_semana", "hora": 18}
    assert len(body["zonas"]) == 1 and body["modelo_version"] == "test"
    z = body["zonas"][0]
    assert z["demand_density"] == 432.1 and z["n_celdas"] == 4
    hist = client.get("/inferencias")
    assert hist.status_code == 200 and len(hist.json()) == 1

def test_bucket_vacio_devuelve_lista_vacia():
    client = _client()
    r = client.post("/inferencias", json={"municipio": 1, "dia_semana": 3, "hora": 3})
    assert r.status_code == 200 and r.json()["zonas"] == []

def test_input_invalido_422():
    client = _client()
    assert client.post("/inferencias", json={"municipio": 1, "dia_semana": 9, "hora": 18}).status_code == 422
