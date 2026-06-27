# API — Microservicio de Zonas Calientes

Servicio REST de **inferencia** de zonas calientes (dónde habrá más demanda de viajes), dado
`municipio`, `dia_semana` y `hora`. El modelo es **no supervisado** (filtro de alta demanda +
DBSCAN haversine), entrenado offline y servido desde el registry de MLflow.

- **Base URL (local):** `http://localhost:8000`
- **Documentación interactiva (Swagger UI):** `GET /docs`
- **Especificación OpenAPI:** `GET /openapi.json` (también en `documentation/openapi.json`)
- **Colección de pruebas:** `insomnia/zonas-calientes.insomnia.json` (importar en Insomnia)
- **Autenticación:** ninguna por ahora (la API key es una fase posterior de endurecimiento).

---

## `GET /health`

Estado del servicio y del modelo cargado.

**200 OK**
```json
{ "status": "ok", "modelo_cargado": true, "version": "1" }
```
- `modelo_cargado`: `false` si el servicio arrancó sin un modelo registrado (hay que entrenar).
- `version`: versión numérica del modelo cargado desde el registry, o `null`.

---

## `POST /inferencias`

Ejecuta la inferencia para un bucket `(municipio, dia_tipo, hora)` y **guarda** el resultado.

**Request** (`application/json`)
```json
{ "municipio": 1, "dia_semana": 3, "hora": 18 }
```

| Campo | Tipo | Rango | Descripción |
|---|---|---|---|
| `municipio` | int | — | Identificador del municipio. |
| `dia_semana` | int | 0–6 | 0 = lunes … 6 = domingo. Se deriva `dia_tipo` (entre_semana / fin_de_semana). |
| `hora` | int | 0–23 | Hora exacta (las horas pico importan). |

**200 OK**
```json
{
  "municipio": 1,
  "bucket": { "dia_tipo": "entre_semana", "hora": 18 },
  "zonas": [
    {
      "lat": 16.751639, "lng": -93.116005, "intensidad": 1.0,
      "demand_density": 1036.51, "supply_demand_ratio": 0.139,
      "n_requests": 653, "n_celdas": 7, "radio_m": 411.7
    }
  ],
  "modelo_version": "1",
  "generado_en": "2026-06-26T18:00:00.000000+00:00"
}
```

Campos de cada **zona** (ordenadas por `demand_density` desc):

| Campo | Descripción |
|---|---|
| `lat`, `lng` | Centro de la zona (centroide de sus celdas, ponderado por demanda). |
| `intensidad` | 0–1: densidad relativa dentro del bucket (1 = la más caliente). Útil para dimensionar el marcador en el mapa. |
| `demand_density` | Solicitudes/km² (media de las celdas de la zona). |
| `supply_demand_ratio` | Oferta/demanda; **bajo** = la demanda rebasa a la oferta (zona más accionable). |
| `n_requests` | Solicitudes totales agregadas de la zona. |
| `n_celdas` | Nº de celdas de grid (300 m) agrupadas en la zona. |
| `radio_m` | Radio aproximado de la zona en metros. |

**Otros códigos**
- `422 Unprocessable Entity` — entrada inválida (p. ej. `dia_semana` o `hora` fuera de rango).
- `503 Service Unavailable` — el modelo no está cargado (`{ "detail": "modelo no disponible" }`); entrena y reinicia.
- `200` con `"zonas": []` — bucket sin zonas calientes (válido, no es error).

---

## `GET /inferencias`

Historial paginado de las inferencias guardadas.

**Query params:** `municipio` (opcional), `limit` (1–200, default 50), `offset` (≥0, default 0).

**200 OK**
```json
[
  {
    "id": 12,
    "municipio": 1,
    "input": { "dia_semana": 3, "hora": 18 },
    "output": { "zonas": [ ... ] },
    "modelo_version": "1",
    "creado_en": "2026-06-26T18:00:00.000000+00:00"
  }
]
```

Devuelve las inferencias más recientes primero. Cumple el requisito de **almacenar** las
inferencias y **consultar el historial**.
