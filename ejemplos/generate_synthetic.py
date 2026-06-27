#!/usr/bin/env python3
"""
Generador de dataset sintético inmobiliario para clustering.
Referencia: 01-especificacion-dominio-y-esquema.md
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

BASE_DIR = Path(__file__).resolve().parent

STUDENT_COLUMNS = [
    "id_listado",
    "fecha_publicacion",
    "dias_en_mercado",
    "estado_listado",
    "tipo_inmueble",
    "metros_construccion",
    "metros_terreno",
    "recamaras",
    "banos",
    "estacionamientos",
    "antiguedad_anios",
    "nivel_piso",
    "tiene_elevador",
    "zona",
    "colonia",
    "distancia_centro_km",
    "indice_seguridad",
    "indice_servicios",
    "precio_venta",
    "precio_m2",
    "mantenimiento_mensual",
    "amueblado",
    "tipo_vendedor",
    "comision_pct",
    "amenidad_alberca",
    "amenidad_jardin",
    "amenidad_seguridad_privada",
    "amenidad_cowork",
]

ANOMALY_TYPES = ["A1", "A2", "A3", "A5", "A7"]


def load_config(path: Path | None = None) -> dict:
    path = path or BASE_DIR / "02-config-generacion.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_catalogs() -> tuple[pd.DataFrame, pd.DataFrame]:
    zonas = pd.read_csv(BASE_DIR / "zonas.csv")
    colonias = pd.read_csv(BASE_DIR / "colonias.csv")
    return zonas, colonias


def _weighted_choice(rng: np.random.Generator, options: list, weights: list) -> np.ndarray:
    return rng.choice(options, size=len(weights) if isinstance(weights, int) else None, p=weights)


def _truncated_normal(
    rng: np.random.Generator, n: int, mean: float, std: float, low: float, high: float
) -> np.ndarray:
    values = rng.normal(mean, std, n)
    return np.clip(values, low, high)


def _spring_weighted_dates(
    rng: np.random.Generator, n: int, start: str, end: str
) -> pd.Series:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    days = (end_ts - start_ts).days
    offsets = rng.integers(0, days + 1, n)
    dates = start_ts + pd.to_timedelta(offsets, unit="D")
    months = dates.month
    spring_boost = np.isin(months, [3, 4, 5])
    extra = rng.integers(0, 45, n)
    dates = dates + pd.to_timedelta(extra * spring_boost, unit="D")
    dates = pd.Series(dates).clip(lower=start_ts, upper=end_ts)
    return dates.dt.strftime("%Y-%m-%d")


def generate_base_frame(
    n: int, rng: np.random.Generator, config: dict, zonas: pd.DataFrame, colonias: pd.DataFrame
) -> pd.DataFrame:
    tipo_cfg = config["tipo_inmueble"]
    tipos = list(tipo_cfg.keys())
    tipo_probs = [tipo_cfg[t] for t in tipos]
    tipo = rng.choice(tipos, size=n, p=tipo_probs)

    colonia_rows = colonias.sample(n, replace=True, random_state=int(rng.integers(0, 2**31)))
    colonia = colonia_rows["colonia"].to_numpy()
    zona = colonia_rows["zona"].to_numpy()
    zona_series = pd.Series(zona)

    zona_lookup = zonas.set_index("zona")
    dist_base = zona_series.map(zona_lookup["distancia_centro_media_km"]).astype(float).to_numpy()
    distancia = np.clip(dist_base + rng.normal(0, 2.5, n), 0.5, 35)

    ind_seg_base = zona_series.map(zona_lookup["indice_seguridad_medio"]).astype(float).to_numpy()
    indice_seguridad = np.clip(ind_seg_base + rng.normal(0, 0.9, n), 1, 10)

    ind_serv_base = zona_series.map(zona_lookup["indice_servicios_medio"]).astype(float).to_numpy()
    indice_servicios = np.clip(ind_serv_base + rng.normal(0, 0.8, n), 1, 10)

    m_cfg = config["metros_construccion"]
    metros = np.empty(n)
    for t in tipos:
        mask = tipo == t
        c = m_cfg[t]
        metros[mask] = _truncated_normal(rng, mask.sum(), c["mean"], c["std"], c["min"], c["max"])

    recamaras = np.zeros(n, dtype=int)
    for t in ("casa", "departamento"):
        mask = tipo == t
        rec = rng.poisson(2.5, mask.sum())
        recamaras[mask] = np.clip(rec + 1, 1, 6)

    banos = np.floor(recamaras / 2) + rng.choice([0, 0.5, 1.0], size=n, p=[0.4, 0.3, 0.3])
    banos = np.clip(banos, 0, 5.5)

    estacionamientos = np.clip(rng.poisson(1.2, n), 0, 4)
    estacionamientos[tipo == "casa"] = np.clip(rng.poisson(2.0, (tipo == "casa").sum()), 0, 4)
    premium = np.isin(zona, ["norte_residencial", "turistica", "centro"])
    estacionamientos[premium] = np.clip(estacionamientos[premium] + 1, 0, 4)

    antiguedad = np.clip(rng.integers(0, 45, n), 0, 60)
    antiguedad[np.isin(zona, ["centro", "oriente_residencial"])] = np.clip(
        rng.integers(5, 55, (np.isin(zona, ["centro", "oriente_residencial"])).sum()), 0, 60
    )
    antiguedad[np.isin(zona, ["norte_residencial", "turistica"])] = np.clip(
        rng.integers(0, 12, (np.isin(zona, ["norte_residencial", "turistica"])).sum()), 0, 60
    )

    nivel_piso = np.full(n, np.nan)
    depto_mask = tipo == "departamento"
    nivel_piso[depto_mask] = rng.integers(0, 16, depto_mask.sum())

    tiene_elevador = np.full(n, np.nan)
    tiene_elevador[depto_mask] = rng.random(depto_mask.sum()) < 0.35
    high_floor = depto_mask & (nivel_piso > 3)
    old_build = depto_mask & (antiguedad > 12)
    need_elev = high_floor & old_build
    tiene_elevador[need_elev] = rng.random(need_elev.sum()) < 0.92

    metros_terreno = np.full(n, np.nan)
    casa_mask = tipo == "casa"
    local_mask = tipo == "local"
    metros_terreno[casa_mask] = _truncated_normal(
        rng, casa_mask.sum(), 220, 120, 50, 2000
    )
    local_terreno = rng.random(local_mask.sum()) < 0.35
    metros_terreno[local_mask] = np.where(
        local_terreno,
        _truncated_normal(rng, local_mask.sum(), 150, 80, 50, 800),
        np.nan,
    )

    p_alberca = np.where(premium, 0.35, 0.08)
    p_jardin = np.where(tipo == "casa", 0.55, 0.05)
    p_seg = np.clip((indice_seguridad - 4) / 12, 0.05, 0.7)
    p_cowork = np.where(
        depto_mask & np.isin(zona, ["centro", "turistica"]) & (antiguedad < 8),
        0.4,
        0.03,
    )
    amenidad_alberca = rng.random(n) < p_alberca
    amenidad_jardin = rng.random(n) < p_jardin
    amenidad_seguridad_privada = rng.random(n) < p_seg
    amenidad_cowork = rng.random(n) < p_cowork

    vendedor_cfg = config["tipo_vendedor"]
    vendedores = list(vendedor_cfg.keys())
    vendedor_p = [vendedor_cfg[v] for v in vendedores]
    tipo_vendedor = rng.choice(vendedores, size=n, p=vendedor_p)

    comision_pct = np.zeros(n)
    comision_pct[tipo_vendedor == "inmobiliaria"] = rng.uniform(3.0, 6.0, (tipo_vendedor == "inmobiliaria").sum())
    comision_pct[tipo_vendedor == "constructora"] = rng.uniform(2.0, 4.0, (tipo_vendedor == "constructora").sum())

    amueblado = rng.random(n) < np.where(
        depto_mask & np.isin(zona, ["turistica", "centro"]), 0.35, 0.12
    )

    mantenimiento = np.full(n, np.nan)
    mantenimiento[depto_mask] = rng.uniform(800, 12000, depto_mask.sum())
    mantenimiento[casa_mask] = rng.uniform(0, 2500, casa_mask.sum())

    fecha = _spring_weighted_dates(rng, n, config["fecha_inicio"], config["fecha_fin"])

    df = pd.DataFrame(
        {
            "id_listado": [f"LST-{i:06d}" for i in range(1, n + 1)],
            "fecha_publicacion": fecha,
            "tipo_inmueble": tipo,
            "zona": zona,
            "colonia": colonia,
            "metros_construccion": metros,
            "metros_terreno": metros_terreno,
            "recamaras": recamaras,
            "banos": banos,
            "estacionamientos": estacionamientos,
            "antiguedad_anios": antiguedad,
            "nivel_piso": nivel_piso,
            "tiene_elevador": tiene_elevador,
            "distancia_centro_km": distancia,
            "indice_seguridad": indice_seguridad,
            "indice_servicios": indice_servicios,
            "tipo_vendedor": tipo_vendedor,
            "comision_pct": comision_pct,
            "amueblado": amueblado,
            "mantenimiento_mensual": mantenimiento,
            "amenidad_alberca": amenidad_alberca,
            "amenidad_jardin": amenidad_jardin,
            "amenidad_seguridad_privada": amenidad_seguridad_privada,
            "amenidad_cowork": amenidad_cowork,
        }
    )
    return df


def compute_prices(df: pd.DataFrame, config: dict, zonas: pd.DataFrame) -> pd.DataFrame:
    pm = config["precio_model"]
    rng = np.random.default_rng(config["random_seed"] + 1)
    zona_beta = zonas.set_index("zona")["beta_zona_log"]
    zona_m2 = zonas.set_index("zona")["precio_m2_base"]

    log_m = np.log(df["metros_construccion"].clip(lower=1))
    beta_z = df["zona"].map(zona_beta).fillna(0).to_numpy()
    beta_t = df["tipo_inmueble"].map(pm["beta_tipo"]).fillna(0).to_numpy()
    m2_scale = np.log(df["zona"].map(zona_m2).fillna(25000) / 25000)

    amen_bonus = np.zeros(len(df))
    for col, bonus in pm["amenidad_bonus"].items():
        amen_bonus += df[col].astype(float).to_numpy() * bonus

    ant_pen = pm["antiguedad_penalty_pct"] * np.minimum(df["antiguedad_anios"].fillna(0), 40)
    est_bonus = pm["estacionamiento_bonus_pct"] * df["estacionamientos"].fillna(0)

    eps = rng.normal(0, pm["sigma_epsilon"], len(df))
    log_p = (
        pm["beta_0"]
        + pm["beta_1"] * log_m
        + pm["beta_2"] * df["indice_servicios"]
        + pm["beta_3"] * df["indice_seguridad"]
        + beta_z
        + beta_t
        + m2_scale * 0.45
        + amen_bonus
        - ant_pen
        + est_bonus
        + eps
    )
    df = df.copy()
    df["precio_venta"] = np.exp(log_p).round(2)
    df["precio_m2"] = (df["precio_venta"] / df["metros_construccion"]).round(2)
    return df


def assign_estado_y_dias(df: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    df = df.copy()
    p75 = df.groupby(["tipo_inmueble", "zona"])["precio_m2"].transform(lambda s: s.quantile(0.75))
    overpriced = df["precio_m2"] > p75

    dias = rng.lognormal(mean=4.2, sigma=0.55, size=len(df)).astype(int)
    dias = np.clip(dias, 1, 730)
    dias[overpriced] = np.clip((dias[overpriced] * rng.uniform(1.4, 2.8, overpriced.sum())).astype(int), 1, 730)
    df["dias_en_mercado"] = dias

    med = df.groupby(["tipo_inmueble", "zona"])["precio_m2"].transform("median")
    competitive = df["precio_m2"] <= med
    estado_cfg = config["estado_listado"]
    estados = []
    for comp in competitive:
        if comp:
            p = [estado_cfg["activo"], estado_cfg["vendido"], estado_cfg["retirado"]]
            p = np.array(p) / np.sum(p)
            p[1] += 0.12
            p = p / p.sum()
        else:
            p = np.array([estado_cfg["activo"], estado_cfg["vendido"], estado_cfg["retirado"]])
            p = p / p.sum()
        estados.append(rng.choice(["activo", "vendido", "retirado"], p=p))
    df["estado_listado"] = estados
    return df


def inject_nulls(df: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    df = df.copy()
    rates = config["null_rates"]
    n = len(df)

    for col, rate in rates.items():
        if col not in df.columns:
            continue
        mask = rng.random(n) < rate
        if df[col].dtype == bool or str(df[col].dtype) == "boolean":
            df[col] = df[col].astype(object)
        df.loc[mask, col] = np.nan

    # MAR: más nulos en mantenimiento para casas
    casa = df["tipo_inmueble"] == "casa"
    mar_mask = casa & (rng.random(n) < 0.05)
    df.loc[mar_mask, "mantenimiento_mensual"] = np.nan

    # MNAR: más nulos en indice_seguridad en periferia
    periferia = df["zona"].str.startswith("periferia")
    mnar_mask = periferia & (rng.random(n) < 0.05)
    df.loc[mnar_mask, "indice_seguridad"] = np.nan

    return df


def inject_anomalies(
    df: pd.DataFrame, config: dict, rng: np.random.Generator
) -> tuple[pd.DataFrame, pd.Series]:
    df = df.copy()
    n = len(df)
    p = config["p_anomaly"]
    anomaly_count = max(1, int(round(n * p)))
    idx = rng.choice(n, size=anomaly_count, replace=False)
    flags = pd.Series(False, index=df.index)
    types_col = pd.Series("", index=df.index, dtype=str)

    for i in idx:
        chosen = rng.choice(ANOMALY_TYPES, size=rng.integers(1, 3), replace=False)
        flags.iloc[i] = True
        types_col.iloc[i] = ";".join(sorted(chosen))

        if "A1" in chosen:
            mult = rng.choice([rng.uniform(3, 5), rng.uniform(0.15, 0.25)])
            df.at[i, "precio_venta"] = round(df.at[i, "precio_venta"] * mult, 2)
            if pd.notna(df.at[i, "metros_construccion"]):
                df.at[i, "precio_m2"] = round(df.at[i, "precio_venta"] / df.at[i, "metros_construccion"], 2)

        if "A2" in chosen and df.at[i, "tipo_inmueble"] == "departamento":
            df.at[i, "metros_terreno"] = round(rng.uniform(20, 120), 2)

        if "A3" in chosen:
            df.at[i, "recamaras"] = 15
            df.at[i, "banos"] = 0.0

        if "A5" in chosen:
            df.at[i, "fecha_publicacion"] = "2026-12-01"

        if "A7" in chosen:
            if rng.random() < 0.5:
                df.at[i, "antiguedad_anios"] = -1
            else:
                df.at[i, "estacionamientos"] = 99

    df["flag_anomalia"] = flags
    df["tipos_anomalia"] = types_col
    return df, flags


def inject_duplicates(
    df: pd.DataFrame, config: dict, rng: np.random.Generator
) -> pd.DataFrame:
    df = df.copy()
    n = len(df)
    dup_cfg = config["duplicados"]
    n_exact = int(round(n * dup_cfg["exactos_pct"]))
    n_relist = int(round(n * dup_cfg["relistados_pct"]))

    extras = []
    next_id = n + 1

    if n_exact > 0:
        src = df.sample(n_exact, replace=True, random_state=int(rng.integers(0, 2**31)))
        exact = src.copy()
        exact["id_listado"] = [f"LST-{i:06d}" for i in range(next_id, next_id + n_exact)]
        next_id += n_exact
        exact["flag_anomalia"] = True
        exact["tipos_anomalia"] = "A4"
        extras.append(exact)

    if n_relist > 0:
        src = df.sample(n_relist, replace=True, random_state=int(rng.integers(0, 2**31)))
        relist = src.copy()
        relist["id_listado"] = [f"LST-{i:06d}" for i in range(next_id, next_id + n_relist)]
        relist["precio_venta"] = (relist["precio_venta"] * rng.uniform(0.98, 1.02, n_relist)).round(2)
        relist["precio_m2"] = (relist["precio_venta"] / relist["metros_construccion"]).round(2)
        relist["flag_anomalia"] = True
        relist["tipos_anomalia"] = "A4"
        extras.append(relist)

    if extras:
        df = pd.concat([df, *extras], ignore_index=True)
    return df


def cast_output_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    bool_cols = [
        "tiene_elevador",
        "amueblado",
        "amenidad_alberca",
        "amenidad_jardin",
        "amenidad_seguridad_privada",
        "amenidad_cowork",
        "flag_anomalia",
    ]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].astype("boolean")
    int_cols = ["recamaras", "estacionamientos", "antiguedad_anios", "dias_en_mercado"]
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    if "nivel_piso" in df.columns:
        df["nivel_piso"] = pd.to_numeric(df["nivel_piso"], errors="coerce").astype("Int64")
    return df


def validate_dataset(df: pd.DataFrame, config: dict) -> dict:
    n = len(df)
    tipo_dist = df["tipo_inmueble"].value_counts(normalize=True)
    target = config["tipo_inmueble"]
    tipo_ok = all(abs(tipo_dist.get(k, 0) - target[k]) <= 0.05 for k in target)

    non_anom = ~df.get("flag_anomalia", False).fillna(False)
    coherent = df.loc[non_anom & df["metros_construccion"].notna()]
    if len(coherent) > 0:
        calc = (coherent["precio_venta"] / coherent["metros_construccion"]).round(2)
        precio_ok = (calc - coherent["precio_m2"]).abs().lt(0.05).mean() >= 0.95
    else:
        precio_ok = True

    anomaly_pct = df.get("flag_anomalia", pd.Series(False, index=df.index)).fillna(False).mean()

    return {
        "n_rows": n,
        "unique_ids": df["id_listado"].nunique() == n,
        "tipo_distribucion_ok": bool(tipo_ok),
        "tipo_distribucion": {k: round(float(tipo_dist.get(k, 0)), 4) for k in target},
        "precio_m2_coherente_pct": round(float(precio_ok) * 100, 2),
        "anomalias_pct": round(float(anomaly_pct) * 100, 2),
    }


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_dataset(config_path: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    config = load_config(config_path)
    zonas, colonias = load_catalogs()
    rng = np.random.default_rng(config["random_seed"])
    n = config["n_rows"]

    df = generate_base_frame(n, rng, config, zonas, colonias)
    df = compute_prices(df, config, zonas)
    df = assign_estado_y_dias(df, config, rng)
    df = inject_nulls(df, config, rng)
    df, _ = inject_anomalies(df, config, rng)
    df = inject_duplicates(df, config, rng)
    df = cast_output_types(df)

    professor = df.copy()
    student = df[STUDENT_COLUMNS].copy()

    validation = validate_dataset(professor, config)
    return student, professor, validation


def save_outputs(
    student: pd.DataFrame,
    professor: pd.DataFrame,
    config: dict,
    validation: dict,
    out_dir: Path | None = None,
) -> dict:
    out_dir = out_dir or BASE_DIR
    salida = config["salida"]
    student_path = out_dir / salida["estudiantes"]
    professor_path = out_dir / salida["profesor"]
    manifest_path = out_dir / salida["manifest"]

    student.to_csv(student_path, index=False, encoding="utf-8")
    professor.to_csv(professor_path, index=False, encoding="utf-8")

    manifest = {
        "version": "0.1",
        "generado_en": datetime.now().isoformat(timespec="seconds"),
        "random_seed": config["random_seed"],
        "n_rows": len(student),
        "p_null_global": config["p_null_global"],
        "p_anomaly": config["p_anomaly"],
        "fecha_inicio": config["fecha_inicio"],
        "fecha_fin": config["fecha_fin"],
        "archivo_estudiantes": salida["estudiantes"],
        "archivo_profesor": salida["profesor"],
        "hash_estudiantes": file_sha256(student_path),
        "validacion": validation,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return manifest


def main() -> None:
    config = load_config()
    student, professor, validation = generate_dataset()
    manifest = save_outputs(student, professor, config, validation)

    print(f"Generados {len(student)} registros.")
    print(f"  Estudiantes: {config['salida']['estudiantes']}")
    print(f"  Profesor:    {config['salida']['profesor']}")
    print(f"  Manifest:    {config['salida']['manifest']}")
    print("Validación:", json.dumps(validation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
