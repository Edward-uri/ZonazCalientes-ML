Microservicio FastAPI de Zonas Calientes ML para ViajeSeguro.

Correr (dev): `uvicorn app.main:app --reload`
Tests: `py -m pytest -q`

---

## Operación

### 1. Levantar el stack completo (FastAPI + MLflow + Postgres)

```bash
cp .env.example .env
docker compose up -d
```

El stack levanta tres servicios:
- **api** (puerto 8000): FastAPI con el endpoint de inferencias y Swagger en `/docs`.
- **mlflow** (puerto 5000): servidor de tracking y model registry.
- **db** (Postgres 16): base de datos analítica propia (nunca la BD transaccional del backend).

### 2. Entrenar y registrar el modelo (job offline)

El l dataset del Nivel B
(`documentation/demanda_agregada_profesor.csv`), nunca la BD transaccional.

```powershell
# Con el stack levantado (PowerShell / Windows):
$env:MLFLOW_TRACKING_URI="http://localhost:5000"; py -m training.train
```

> En Linux/macOS: `MLFLOW_TRACKING_URI=http://localhost:5000 python -m training.train`

El job filtra celdas de alta demanda + corre DBSCAN haversine por bucket
`(municipio, dia_tipo, hora)` y registra el artefacto como `zonas-calientes` en MLflow.

### 3. Recargar el modelo

El servicio carga el modelo al arrancar (lifespan de FastAPI). Para que tome
una nueva versión registrada, reinicia el contenedor:

```bash
docker compose restart api
```

### 4. Notas de despliegue en Coolify

Configura los tres servicios con los volúmenes `mlflow_data` y `db_data` para
persistencia entre reinicios. Las variables de entorno obligatorias son:

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | URL de Postgres (ver `.env.example`) |
| `MLFLOW_TRACKING_URI` | URL del servidor MLflow interno |

El flujo de operación es:
1. Levantar stack → 2. Correr job de entrenamiento → 3. Reiniciar `api` → 4. Inferir via `POST /inferencias`.
