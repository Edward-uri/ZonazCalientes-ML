from pathlib import Path
import pandas as pd

COLUMNAS_DEMANDA = [
    "cell_id", "municipio", "time_bucket", "dia_tipo", "hour",
    "centroid_lat", "centroid_lon", "n_requests", "n_drivers_available",
    "supply_demand_ratio", "demand_density",
]

# app/infrastructure/data/demanda.py -> parents[3] = raíz del repo
RUTA_DEMANDA_DEFAULT = Path(__file__).resolve().parents[3] / "documentation" / "demanda_agregada_profesor.csv"

def cargar_demanda(ruta: str | Path = RUTA_DEMANDA_DEFAULT) -> pd.DataFrame:
    df = pd.read_csv(ruta)
    faltan = [c for c in COLUMNAS_DEMANDA if c not in df.columns]
    if faltan:
        raise ValueError(f"El dataset Nivel B no tiene las columnas requeridas: {faltan}")
    return df
