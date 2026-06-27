from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.infrastructure.api.routers import health, inferencias
from app.infrastructure.db.session import init_db
from app.infrastructure.ml.modelo import ModeloZonasMlflow

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    modelo = ModeloZonasMlflow()
    try:
        modelo.cargar()
        app.state.modelo = modelo
    except Exception:
        app.state.modelo = None  # arranca sin modelo; /health lo reporta
    yield

app = FastAPI(title="Zonas Calientes ML", version="0.1.0", lifespan=lifespan)
app.state.modelo = None
app.include_router(health.router)
app.include_router(inferencias.router)
