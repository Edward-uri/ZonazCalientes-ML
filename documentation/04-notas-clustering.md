# 04 — Notas de clustering (zonas calientes, no supervisado)

Notas de diseño y resultados del notebook `notebooks/clustering.ipynb`. Todo el
modelado es **no supervisado** (DBSCAN, NearestNeighbors, LocalOutlierFactor, KMeans);
el *ground-truth* (`zone_id_true`, `is_hot_true`) sólo se usa para **validar** al final,
nunca como feature.

Bucket de análisis: `dia_tipo = entre_semana`, `hour = 18` (hora pico de salida laboral).
Todo el pipeline se ajusta **por municipio** (cada municipio tiene su propia geografía y
escala de demanda).

---

## 1. Dos niveles y por qué el Nivel B mejora sobre los puntos crudos

| | **Nivel A — baseline de puntos** | **Nivel B — modelo** |
|---|---|---|
| Entrada | cada solicitud `(lat, lng)` | una fila por celda × franja × municipio |
| Features | sólo ubicación | `[centroid_lat, centroid_lon, demand_density, supply_demand_ratio]` |
| Distancia | haversine (geo pura), coords en radianes | euclidiana sobre features estandarizadas |
| Escalado | **no** (haversine puro) | **sí** (`StandardScaler` a las 4) |
| Qué responde | *dónde caen físicamente los puntos* | *dónde la demanda es alta y/o la oferta escasea* |

El baseline de puntos agrupa por **densidad espacial**: recupera la forma de las zonas,
pero no distingue una zona caliente de una fría — todas las solicitudes "pesan" igual.
El **Nivel B** añade las dos señales que de verdad le importan al conductor:
`demand_density` (cuánta demanda por km²) y `supply_demand_ratio` (presión oferta/demanda;
bajo = demanda > oferta). Por eso un cluster del Nivel B **es** una zona caliente
operativa, no sólo un punto concurrido.

## 2. Features elegidas

`[centroid_lat, centroid_lon, demand_density, supply_demand_ratio]`.

- Las **coordenadas** mantienen los clusters espacialmente contiguos (una zona caliente
  es una mancha geográfica, no celdas dispersas).
- `demand_density` = demanda normalizada por área de celda.
- `supply_demand_ratio` = `n_drivers / max(n_requests, 1)`; capta la *escasez de oferta*,
  que es lo que hace accionable a una zona caliente.

No se incluyen `n_requests`/`n_drivers` crudos (redundantes con density/ratio) ni
`cancel_rate` (más ruidoso y correlacionado). Nunca se incluye el *ground-truth*.

## 3. Por qué se escala en B pero no en el baseline haversine

- **Baseline (A):** la distancia es **haversine** sobre `(lat, lng)` en radianes — una
  métrica geográfica con unidades homogéneas (radianes → metros). Escalar
  distorsionaría las distancias reales en el terreno, así que **no se escala**.
- **Modelo (B):** la distancia es **euclidiana** y mezcla unidades heterogéneas: grados
  de lat/lon (rango ~0.1) con densidades (rango ~10–4500) y ratios (~0–9). Sin
  estandarizar, `demand_density` dominaría la distancia y la geografía sería irrelevante.
  `StandardScaler` lleva las 4 features a media 0 / desviación 1, de modo que cada una
  aporta por igual. Esta diferencia (haversine sin escala vs euclidiana escalada) es
  deliberada y está documentada en el notebook.

## 4. Calibración de `eps` por kNN (no supervisado)

`eps` se calibra con el método clásico de **k-distancias**, sin etiquetas:

1. `NearestNeighbors(n_neighbors=min_samples)` → distancia de cada celda a su
   `min_samples`-ésimo vecino más cercano (sobre la matriz escalada).
2. Se ordenan esas distancias y se busca el **codo** de la curva: el punto de **máxima
   distancia por debajo de la cuerda** que une los extremos.
3. **Robustez:** antes de medir el codo se recorta el **2 % superior** de la cola. Sin
   este recorte, unas pocas celdas extremadamente aisladas (p. ej. un `supply_demand_ratio`
   atípico) tuercen la cuerda y empujan `eps` a un valor absurdo (en el municipio 2,
   sin recorte el codo caía en el último punto → `eps ≈ 4.7`, un único cluster inútil).
   Con recorte, el codo queda estable en ambos municipios.

`min_samples = 4` (densidad mínima de un cluster en el espacio de 4 features).

**`eps` calibrado:** municipio 1 → `0.420`; municipio 2 → `0.394`.

## 5. DBSCAN sobre Nivel B

`DBSCAN(eps, min_samples=4, metric="euclidean")` sobre la matriz escalada. Las celdas con
`cluster != -1` son **candidatas a zona caliente**; el ruido (`-1`) es mayormente el
"fondo" de celdas de una sola solicitud.

| Municipio | clusters | ruido | celdas |
|---|---|---|---|
| 1 | 2 | 123 | 134 |
| 2 | 5 | 117 | 138 |

## 6. Rol de LOF (no supervisado)

En un **único** bucket, las celdas verdaderamente calientes son **pocas y de valores
extremos** (densidad muy alta, ratio muy bajo): se comportan como **anomalías**, no como
un cluster denso. `LocalOutlierFactor` las detecta por contraste de densidad local. Sus
*outliers* **coinciden por completo con el ruido de DBSCAN**:

| Municipio | outliers LOF | ruido DBSCAN | coinciden |
|---|---|---|---|
| 1 | 7 | 123 | 7 / 7 |
| 2 | 5 | 117 | 5 / 5 |

Esto confirma la lectura: en un solo bucket, "zona caliente" ≈ "anomalía de demanda".
Agregando varios buckets (lo que hará el microservicio) las zonas calientes se vuelven
densas y DBSCAN las agrupa como clusters propios.

## 7. KMeans baseline

`KMeans` con `k` elegido por **codo de inercia + silhouette** (ambos no supervisados).
`k* = 6` (muni 1, silhouette 0.30) y `k* = 2` (muni 2, silhouette 0.61). KMeans logra
buen silhouette separando "fondo vs picos", pero al asignar **todas** las celdas a algún
cluster no aísla las calientes tan limpiamente como DBSCAN (que manda el fondo a ruido).

## 8. Resultados de validación (por municipio)

Métricas calculadas **sólo para medir** (no entrenan el modelo):

| Municipio | clusters | ARI vs `zone_id_true` | NMI | precision hot | recall hot | F1 hot | silhouette |
|---|---|---|---|---|---|---|---|
| 1 | 2 | **0.193** | **0.430** | **0.727** | 0.421 | 0.533 | -0.113 |
| 2 | 5 | **0.149** | **0.367** | **0.333** | 0.538 | 0.412 | -0.200 |

Baseline de puntos (Nivel A, haversine) para comparar:

| Municipio | ARI vs `zone_id_true` | NMI |
|---|---|---|
| 1 | 1.000 | 1.000 |
| 2 | 1.000 | 1.000 |

**Lectura honesta de los números:**

- El **baseline A** logra ARI = 1.0 porque recupera la **geometría** de zonas gaussianas:
  es un problema fácil que sólo usa ubicación. No identifica zonas *calientes*, sólo
  densas — responde la pregunta equivocada para el negocio.
- **DBSCAN B** opera sobre la superficie de demanda agregada, mucho más ruidosa (un fondo
  enorme de celdas de 1 solicitud con densidad idéntica ~11). Su ARI/NMI es menor en
  absoluto, pero **sus clusters tienen significado operativo**. La **precisión de celdas
  hot** del municipio 1 (0.73) confirma que cuando DBSCAN marca un cluster, suele ser
  efectivamente caliente. En el municipio 2 la precisión baja (0.33) porque DBSCAN
  también engancha pequeños grupos del fondo de baja demanda (ver zonas con
  `frac_hot_true = 0` en la tabla de extracción); el recall sube a 0.54.
- El **silhouette negativo** es esperado y coherente: las celdas hot no forman blobs
  convexos compactos sino picos dispersos sobre un fondo plano; DBSCAN igualmente los
  separa, pero la métrica de cohesión convexa los penaliza.

## 9. Zonas calientes extraídas

Por cluster: centro (centroide), `n_requests` total, `demand_density` media,
`supply_demand_ratio` medio y fracción de celdas hot reales. Se extrajeron **7 zonas**
(2 en muni 1, 5 en muni 2). Las relevantes:

| Muni | cluster | celdas | n_req total | density media | ratio medio | frac_hot |
|---|---|---|---|---|---|---|
| 1 | 0 | 7 | 114 | 181.0 | 0.31 | 0.71 |
| 1 | 1 | 4 | 40 | 111.1 | 0.46 | 0.75 |
| 2 | 3 | 4 | 176 | 488.9 | 0.10 | 1.00 |
| 2 | 1 | 5 | 53 | 117.8 | 0.46 | 0.60 |

(Los otros 3 clusters del municipio 2 — density ~11, ratio alto, `frac_hot = 0` — son
falsos positivos del fondo de baja demanda; el microservicio los filtraría por umbral de
`demand_density` / `supply_demand_ratio`.)

## 10. Parámetros elegidos (resumen reproducible)

- `dia_tipo = entre_semana`, `hour = 18`, `random_seed = 42`.
- Features Nivel B: `[centroid_lat, centroid_lon, demand_density, supply_demand_ratio]`,
  `StandardScaler` a las 4.
- `min_samples = 4`; `eps` por codo de k-distancias con recorte de cola del 2 %
  (muni 1 = 0.420, muni 2 = 0.394).
- Baseline A: `DBSCAN(metric="haversine", eps = 250 m / 6_371_000, min_samples = 8)`,
  coords en radianes, **sin escalar**.
- LOF: `n_neighbors = min(20, n-1)`. KMeans: `k` por codo + silhouette, `n_init = 10`.

## 11. Conclusión

El **baseline de puntos (Nivel A)** gana en la métrica geométrica pura (ARI ≈ 1.0) pero
resuelve un problema de juguete. El **modelo Nivel B** es la pieza útil: agrupa celdas por
**demanda y presión oferta/demanda** con `eps` calibrado de forma no supervisada, y sus
clusters son las zonas calientes que el microservicio expondrá. LOF y la validación
confirman que, en un único bucket, las zonas calientes son anomalías de demanda; al
agregar varios buckets el microservicio las verá como clusters densos estables.
