# Diccionario de Datos
## Dataset de Orígenes de Viaje — Zonas Calientes

**Versión:** 1.0  
**Generador:** `generate_synthetic.py` + `config/02-config-generacion.yaml`  
**Archivos:** `viajes_profesor.csv` (completo) · `viajes_estudiante.csv` (sin columnas de ground-truth)

---

## Tabla de Columnas

| # | Columna | Tipo Python | Dominio / Rango | Regla de Calidad Esperada | Es Ground-Truth |
|---|---|---|---|---|---|
| 1 | `id_viaje` | `str` | Cadena `VJE-NNNNNN` (6 dígitos) | Único en todo el dataset; no nulo; formato regex `^VJE-\d{6}$` | No |
| 2 | `municipio` | `int` | `{1, 2}` | Valor en `{1, 2}`; no nulo; sin otros enteros | No |
| 3 | `fecha` | `str` (ISO 8601 date) | `2026-01-01` a `2026-03-31` | No nulo; formato `YYYY-MM-DD`; dentro del rango de fechas del YAML | No |
| 4 | `dia_semana` | `int` | `[0, 6]` — 0=lunes, 6=domingo | `dia_semana ∈ [0, 6]`; coincide con el día de la semana de `fecha`; no nulo | No |
| 5 | `hora` | `int` | `[0, 23]` en filas normales; puede ser `>23` en anomalías inyectadas | `hora ∈ [0, 23]` en filas con `flag_anomalia = False`; valores `>23` indican anomalía temporal | No |
| 6 | `lat` | `float` | Municipio 1: `[16.70, 16.80]`; Municipio 2: `[16.86, 16.94]` (bbox YAML). Anomalías pueden estar fuera. | `lat` dentro del `bbox[municipio]` en filas normales; 6 decimales de precisión; no nulo (salvo nulos inyectados) | No |
| 7 | `lng` | `float` | Municipio 1: `[-93.16, -93.08]`; Municipio 2: `[-92.12, -92.04]` (bbox YAML). Anomalías pueden estar fuera. | `lng` dentro del `bbox[municipio]` en filas normales; 6 decimales de precisión; no nulo (salvo nulos inyectados) | No |
| 8 | `tipo_servicio` | `str` | `{'normal', 'programado'}` | Valor en `{'normal', 'programado'}`; distribución ~85% normal / 15% programado; puede ser `NaN` (nulos inyectados) | No |
| 9 | `distancia_km` | `float` | `> 0` (lognormal, típicamente 1–15 km) | `distancia_km > 0` en filas sin nulos; distribución lognormal con media geométrica ≈ `exp(0.9)` km; puede ser `NaN` | No |
| 10 | `pasajeros` | `int` | `[1, 4]` | `pasajeros ∈ {1, 2, 3, 4}`; no nulo; distribución Poisson+1 clippeada | No |
| 11 | `costo_mxn` | `float` | `> 0` MXN; típicamente 30–200 | `costo_mxn > 0` en filas sin nulos; correlacionado con `distancia_km`; puede ser `NaN` | No |
| 12 | `lluvia` | `bool` | `{True, False}` | No nulo; `True` en ~15% de filas (probabilidad horaria/estacional) | No |
| 13 | `zona_real` | `int` | `[-1, n_zonas_municipio - 1]`: -1=ruido, 0,1,2=zona plantada | No nulo; `zona_real = -1` en ~8% de filas (ruido); valores `≥ 0` corresponden a zonas definidas en `config/zonas[municipio]` | **Sí** |
| 14 | `flag_anomalia` | `bool` | `{True, False}` | No nulo; `True` en ~2% de filas; filas con `flag_anomalia=True` tienen `lat/lng` fuera de bbox **o** `hora > 23` | **Sí** |

---

## Notas sobre Reglas de Calidad

### Relaciones entre Columnas

- `dia_semana` se deriva de `fecha`: deben coincidir al 100% (`pd.Timestamp(fecha).dayofweek == dia_semana`).
- `costo_mxn` se deriva de `distancia_km`: filas sin nulos deben cumplir `costo_mxn ≈ 25 + distancia_km * 8` (con ruido gaussiano σ=5).
- `zona_real` y `municipio` deben ser consistentes: `zona_real` solo puede tomar índices válidos para ese `municipio` (o -1 para ruido).

### Nulos Esperados (~3% de filas)

Los nulos se inyectan aleatoriamente en:
- `distancia_km`
- `costo_mxn`
- `tipo_servicio`

El resto de columnas no debe tener nulos salvo anomalías extremas.

### Anomalías Esperadas (~2% de filas)

Dos tipos de anomalía geoespaciotemporal:
1. **Coordenada fuera de bbox**: `lat` o `lng` desplazados ±0.5 grados fuera del bbox del municipio.
2. **Hora inválida**: `hora ∈ [24, 29]` (entero generado con `rng.integers(24, 30)`).

Ambos tipos coexisten con `flag_anomalia = True`.

### Duplicados (~1% de filas)

Filas con valores idénticos en todas las columnas (salvo `id_viaje`). El `id_viaje` siempre es único incluso en duplicados.

---

## Columnas Disponibles por Archivo

| Columna | `viajes_estudiante.csv` | `viajes_profesor.csv` |
|---|---|---|
| `id_viaje` | ✓ | ✓ |
| `municipio` | ✓ | ✓ |
| `fecha` | ✓ | ✓ |
| `dia_semana` | ✓ | ✓ |
| `hora` | ✓ | ✓ |
| `lat` | ✓ | ✓ |
| `lng` | ✓ | ✓ |
| `tipo_servicio` | ✓ | ✓ |
| `distancia_km` | ✓ | ✓ |
| `pasajeros` | ✓ | ✓ |
| `costo_mxn` | ✓ | ✓ |
| `lluvia` | ✓ | ✓ |
| `zona_real` | — | ✓ |
| `flag_anomalia` | — | ✓ |
