"""Generador sintético de demanda de viajes (Nivel A crudo + Nivel B agregado) para zonas calientes."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import yaml

R_TIERRA_M = 6_371_000.0
COLS_A = ["request_id","timestamp","municipio","lat","lng","hour","day_of_week",
          "is_weekend","is_holiday","distancia_km","zona_destino","costo_mxn","accepted","zone_id_true"]
COLS_B = ["cell_id","municipio","time_bucket","dia_tipo","hour","centroid_lat","centroid_lon",
          "n_requests","n_drivers_available","supply_demand_ratio","demand_density",
          "cancel_rate","is_hot_true","zone_id_true"]

def cargar_config(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

def _dia_tipo(dow: int) -> str:
    return "fin_de_semana" if dow >= 5 else "entre_semana"

def _peso(hour: int, dia_tipo: str, cfg: dict) -> float:
    base = cfg["demanda_horaria"].get(hour, 0.2)
    if dia_tipo == "fin_de_semana":
        base = max(base, cfg["demanda_finde_noche"].get(hour, 0.0))
    return base

def generar_nivel_a(cfg: dict) -> pd.DataFrame:
    rng = np.random.default_rng(cfg["random_seed"])
    fechas = pd.date_range(cfg["fecha_inicio"], cfg["fecha_fin"], freq="D")
    festivos = set(cfg["festivos"])
    filas: list[dict] = []
    rid = 0
    for muni in cfg["municipios"]:
        zonas = cfg["zonas"][muni]
        pesos = np.array([z["peso"] for z in zonas]); pesos = pesos / pesos.sum()
        bb = cfg["bbox"][muni]
        for fecha in fechas:
            dow = int(fecha.dayofweek); dt = _dia_tipo(dow)
            es_finde = dow >= 5
            es_festivo = fecha.date().isoformat() in festivos
            for hour in range(24):
                n = int(cfg["n_base_por_bucket"] * _peso(hour, dt, cfg) * (1.3 if es_festivo else 1.0))
                for _ in range(n):
                    rid += 1
                    if rng.random() < cfg["frac_ruido"]:
                        lat = rng.uniform(*bb["lat"]); lng = rng.uniform(*bb["lng"]); zona = -1
                    else:
                        zi = int(rng.choice(len(zonas), p=pesos)); z = zonas[zi]
                        sigma_deg = z["sigma_m"] / R_TIERRA_M * (180 / np.pi)
                        lat = z["centro"][0] + rng.normal(0, sigma_deg)
                        lng = z["centro"][1] + rng.normal(0, sigma_deg)
                        zona = zi
                    p_accept = 0.97 - 0.30 * _peso(hour, dt, cfg)   # en pico se atienden menos (más cancelaciones)
                    dist = float(rng.lognormal(0.9, 0.5))
                    minuto = int(rng.integers(60))
                    tarifas_muni = cfg["tarifas"][muni]
                    if rng.random() < cfg["prob_destino_fuera"]:
                        zona_destino, costo = -1, float(cfg["tarifa_fuera"])      # afueras: tarifa de fuera
                    else:
                        zona_destino = int(rng.integers(len(tarifas_muni)))
                        costo = float(tarifas_muni[zona_destino])                 # tarifa FIJA de la zona destino
                    filas.append({
                        "request_id": f"REQ-{rid:06d}",
                        "timestamp": f"{fecha.date().isoformat()}T{hour:02d}:{minuto:02d}:00",
                        "municipio": muni, "lat": round(float(lat), 6), "lng": round(float(lng), 6),
                        "hour": hour, "day_of_week": dow, "is_weekend": es_finde, "is_holiday": es_festivo,
                        "distancia_km": round(dist, 2), "zona_destino": zona_destino, "costo_mxn": costo,
                        "accepted": bool(rng.random() < p_accept), "zone_id_true": zona,
                    })
    df = pd.DataFrame(filas)
    df = df.sample(frac=1.0, random_state=cfg["random_seed"]).reset_index(drop=True)
    df = _inyectar_anomalias(df, rng, cfg)
    df = _inyectar_nulos(df, rng, cfg)
    df = _inyectar_duplicados(df, rng, cfg)
    return df[COLS_A]

def _inyectar_anomalias(df, rng, cfg):
    idx = rng.choice(df.index, size=int(len(df) * cfg["frac_anomalias"]), replace=False)
    for i in idx:
        if rng.random() < 0.5:
            df.at[i, "lat"] = df.at[i, "lat"] + rng.choice([-1, 1]) * 0.5
        else:
            df.at[i, "hour"] = int(rng.integers(24, 30))
    return df

def _inyectar_nulos(df, rng, cfg):
    idx = rng.choice(df.index, size=int(len(df) * cfg["frac_nulos"]), replace=False)
    for i in idx:
        df.at[i, rng.choice(["distancia_km", "costo_mxn"])] = np.nan
    return df

def _inyectar_duplicados(df, rng, cfg):
    k = int(len(df) * cfg["frac_duplicados"])
    if k == 0:
        return df
    return pd.concat([df, df.sample(n=k, random_state=cfg["random_seed"])], ignore_index=True)

def _filas_validas(df_a, cfg):
    """Filtra anomalías (coords fuera de bbox u hora inválida) antes de agregar Nivel B."""
    mask = df_a["hour"].between(0, 23)
    dentro = pd.Series(False, index=df_a.index)
    for muni, bb in cfg["bbox"].items():
        m = df_a["municipio"] == muni
        dentro |= m & df_a["lat"].between(*bb["lat"]) & df_a["lng"].between(*bb["lng"])
    return df_a[mask & dentro].copy()

def agregar_nivel_b(df_a: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    rng = np.random.default_rng(cfg["random_seed"] + 2)
    cell_m = cfg["grid"]["cell_size_m"]
    deg = (180 / np.pi) / R_TIERRA_M           # metros -> grados (aprox)
    cell_deg = cell_m * deg
    area_km2 = (cell_m / 1000.0) ** 2
    val = _filas_validas(df_a, cfg)
    val["dia_tipo"] = val["day_of_week"].map(_dia_tipo)
    filas: list[dict] = []
    for muni in cfg["municipios"]:
        bb = cfg["bbox"][muni]
        sub = val[val["municipio"] == muni].copy()
        sub["row"] = ((sub["lat"] - bb["lat"][0]) / cell_deg).astype(int)
        sub["col"] = ((sub["lng"] - bb["lng"][0]) / cell_deg).astype(int)
        for (r, c, dt, hour), g in sub.groupby(["row", "col", "dia_tipo", "hour"]):
            n_req = len(g)
            n_drivers = int(rng.poisson(cfg["supply"]["base_drivers"]))
            zona = int(g["zone_id_true"].mode().iloc[0])
            is_hot = bool(zona >= 0 and n_req >= cfg["grid"]["min_requests_hot"])
            filas.append({
                "cell_id": f"{muni}-{r}-{c}", "municipio": muni,
                "time_bucket": f"{dt}_{hour:02d}", "dia_tipo": dt, "hour": int(hour),
                "centroid_lat": round(bb["lat"][0] + (r + 0.5) * cell_deg, 6),
                "centroid_lon": round(bb["lng"][0] + (c + 0.5) * cell_deg, 6),
                "n_requests": int(n_req), "n_drivers_available": n_drivers,
                "supply_demand_ratio": round(n_drivers / max(n_req, 1), 3),
                "demand_density": round(n_req / area_km2, 2),
                "cancel_rate": round(1.0 - float(g["accepted"].mean()), 3),
                "is_hot_true": is_hot, "zone_id_true": zona,
            })
    return pd.DataFrame(filas)[COLS_B]

def validar_dataset(df_a: pd.DataFrame, cfg: dict) -> dict:
    fuera = 0
    for muni, bb in cfg["bbox"].items():
        m = df_a["municipio"] == muni
        fuera += int(((df_a.loc[m, "lat"] < bb["lat"][0]) | (df_a.loc[m, "lat"] > bb["lat"][1]) |
                      (df_a.loc[m, "lng"] < bb["lng"][0]) | (df_a.loc[m, "lng"] > bb["lng"][1])).sum())
    return {
        "solicitudes": int(len(df_a)), "nulos": int(df_a.isna().sum().sum()),
        "duplicados": int(df_a.duplicated().sum()),
        "coords_fuera_bbox": fuera, "hora_invalida": int((~df_a["hour"].between(0, 23)).sum()),
    }

def main() -> None:
    cfg = cargar_config("config/02-config-generacion.yaml")
    a = generar_nivel_a(cfg)
    b = agregar_nivel_b(a, cfg)
    out = Path("documentation"); out.mkdir(exist_ok=True)
    a.to_csv(out / "solicitudes_profesor.csv", index=False)
    a.drop(columns=["zone_id_true"]).to_csv(out / "solicitudes_estudiante.csv", index=False)
    b.to_csv(out / "demanda_agregada_profesor.csv", index=False)
    b.drop(columns=["is_hot_true", "zone_id_true"]).to_csv(out / "demanda_agregada_estudiante.csv", index=False)
    manifest = {"seed": cfg["random_seed"], "solicitudes": int(len(a)), "celdas": int(len(b)),
                "celdas_hot": int(b["is_hot_true"].sum()), "validacion": validar_dataset(a, cfg)}
    with open(out / "generation_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"Nivel A: {len(a)} solicitudes. Nivel B: {len(b)} celdas ({manifest['celdas_hot']} hot). {manifest['validacion']}")

if __name__ == "__main__":
    main()
