from sqlmodel import SQLModel, Session, create_engine
from app.infrastructure.db.models import Inferencia
from app.infrastructure.db.repos import InferenciaRepo

def _repo():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return InferenciaRepo(Session(engine))

def test_guardar_y_listar():
    repo = _repo()
    repo.guardar(Inferencia(municipio=1, input={"hora": 18}, output={"zonas": []}, modelo_version="1"))
    repo.guardar(Inferencia(municipio=2, input={"hora": 9}, output={"zonas": []}, modelo_version="1"))
    todos = repo.listar()
    assert len(todos) == 2
    solo1 = repo.listar(municipio=1)
    assert len(solo1) == 1 and solo1[0].municipio == 1

def test_paginacion():
    repo = _repo()
    for h in range(5):
        repo.guardar(Inferencia(municipio=1, input={"hora": h}, output={}, modelo_version="1"))
    page = repo.listar(limit=2, offset=0)
    assert len(page) == 2
