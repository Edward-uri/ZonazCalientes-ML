# Despliegue en Coolify (MLOps)

El stack son **tres servicios** definidos en `docker-compose.yml`:

| Servicio | Imagen | Rol | Puerto |
|---|---|---|---|
| `api` | build desde `Dockerfile` | FastAPI (inferencia + historial + Swagger) | 8000 |
| `mlflow` | `ghcr.io/mlflow/mlflow:v2.17.0` | Tracking + model registry | 5000 |
| `db` | `postgres:16` | BD propia del microservicio (NO la transaccional) | interno |

> El downgrade de `protobuf` que da problemas en local **no aplica aquí**: cada contenedor
> tiene su propio entorno aislado. Por eso el deploy es la forma limpia de correrlo.

---

## A. Crear el recurso en Coolify

1. **Push del repo** a GitHub/GitLab (ya hecho para el análisis; incluye `app/`, `training/`,
   `Dockerfile`, `docker-compose.yml`, `documentation/demanda_agregada_profesor.csv`).
2. En Coolify: **+ New → Docker Compose** (o "Resource → Docker Compose Based").
3. Conecta el repositorio y rama; **Compose file:** `docker-compose.yml`.
4. Coolify construye la imagen `api` desde el `Dockerfile` y baja `mlflow` + `postgres`.
5. **Dominios (NO puertos de host):** el compose usa `expose` (no publica al host) para no
   chocar con los puertos del servidor (el propio Coolify ocupa el 8000). La exposición se hace
   por **dominio + proxy de Coolify**:
   - `api` → en la config del servicio, asigna un **dominio**; Coolify enruta a su puerto 8000.
     Es el endpoint del conductor. **Obligatorio** para que sea accesible.
   - `mlflow` → opcional asignarle otro dominio (puerto 5000) para ver la evidencia de
     entrenamiento; o déjalo interno.
   - Para correr **local** con `localhost:8000`, el repo trae `docker-compose.override.yml` que
     vuelve a publicar los puertos (Coolify lo ignora).
6. **Volúmenes** `mlflow_data` y `db_data` ya están declarados → persisten entre redeploys.

## B. Primer despliegue

7. **Deploy.** Los tres servicios arrancan. `GET /health` responde `200` pero con
   `"modelo_cargado": false` — todavía no hay modelo registrado. Es lo esperado.

## C. Entrenar y registrar el modelo (una vez)

El entrenamiento es **offline** (no corre en el path del servicio). Se ejecuta una vez contra
el MLflow desplegado:

8. En Coolify, abre la **terminal del contenedor `api`** (o usa "Execute Command") y corre:
   ```bash
   python -m training.train
   ```
   > Dentro del contenedor el intérprete es `python` (en local Windows es `py`).
   > El contenedor ya trae `MLFLOW_TRACKING_URI=http://mlflow:5000`, así que registra el modelo
   > `zonas-calientes` en el MLflow del stack. Debe imprimir
   > `Entrenado: N buckets con zonas, M zonas. Métricas: {...}`.
9. (Opcional, evidencia) corre también la validación:
   ```bash
   python -m training.validar
   ```
   Crea un run `validacion` en MLflow con las métricas vs ground-truth.

## D. Cargar el modelo en el servicio

10. **Reinicia el servicio `api`** (Coolify → Restart). En el arranque, el `lifespan` carga
    `models:/zonas-calientes/latest` del registry. Verifica:
    ```
    GET /health  ->  { "status": "ok", "modelo_cargado": true, "version": "1" }
    ```

## E. Probar

11. Importa `insomnia/zonas-calientes.insomnia.json` en Insomnia y cambia la variable de entorno
    `base_url` al dominio público de `api`. Corre:
    - `GET /health`
    - `POST /inferencias` `{ "municipio": 1, "dia_semana": 3, "hora": 18 }`
    - `GET /inferencias` (historial)
12. Swagger en `https://<tu-dominio-api>/docs`.

---

## Reentrenar (cuando lleguen datos nuevos)

Repite **C → D**: corre `python -m training.train` (registra una nueva versión) y reinicia
`api`. Como `MODELO_STAGE=latest`, el servicio toma automáticamente la versión más reciente.

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./zonas.db` (local) | Postgres del microservicio en deploy. |
| `MLFLOW_TRACKING_URI` | `./mlruns` (local) | URL del MLflow del stack en deploy. |
| `MODELO_NOMBRE` | `zonas-calientes` | Nombre del modelo en el registry. |
| `MODELO_STAGE` | `latest` | Versión/alias a cargar. |

## Notas

- **Build local opcional** (con Docker corriendo): `docker compose up -d --build`, luego pasos
  C–E con `python -m training.train` dentro del contenedor `api`
  (`docker compose exec api python -m training.train`).
- **Siguiente endurecimiento** (fase posterior): API key, separar imagen de entrenamiento de la
  de servicio, backend de MLflow en Postgres en vez de SQLite, y el pipeline de eventos (outbox +
  worker) que alimenta datos reales sin PII.
