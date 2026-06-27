from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlmodel import Session
from app.infrastructure.api.schemas import (
    InferenciaRequest,
    InferenciaResponse,
    InferenciaHistorialOut,
)
from app.infrastructure.db.session import get_session
from app.infrastructure.db.repos import InferenciaRepo
from app.application.predecir import PredecirZonasCalientes
from app.application.listar_inferencias import ListarInferencias

router = APIRouter(tags=["inferencias"])

@router.post("/inferencias", response_model=InferenciaResponse)
def crear_inferencia(req: InferenciaRequest, request: Request, session: Session = Depends(get_session)):
    modelo = getattr(request.app.state, "modelo", None)
    if modelo is None or not modelo.disponible():
        raise HTTPException(status_code=503, detail="modelo no disponible")
    caso = PredecirZonasCalientes(modelo, InferenciaRepo(session))
    return caso.ejecutar(req.municipio, req.dia_semana, req.hora)

@router.get("/inferencias", response_model=list[InferenciaHistorialOut])
def listar_inferencias(
    municipio: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    caso = ListarInferencias(InferenciaRepo(session))
    return caso.ejecutar(municipio=municipio, limit=limit, offset=offset)
