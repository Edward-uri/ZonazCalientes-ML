from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])

@router.get("/health")
def health(request: Request):
    modelo = getattr(request.app.state, "modelo", None)
    return {
        "status": "ok",
        "modelo_cargado": modelo is not None and modelo.disponible(),
        "version": modelo.version if modelo is not None else None,
    }
