import pandas as pd
import pytest
from app.infrastructure.data.demanda import cargar_demanda, COLUMNAS_DEMANDA, RUTA_DEMANDA_DEFAULT

def test_carga_csv_real_nivel_b():
    df = cargar_demanda()
    assert len(df) > 0
    for col in COLUMNAS_DEMANDA:
        assert col in df.columns
    assert df["hour"].between(0, 23).all()
    assert set(df["dia_tipo"].unique()) <= {"entre_semana", "fin_de_semana"}

def test_default_apunta_al_csv_del_profesor():
    assert RUTA_DEMANDA_DEFAULT.name == "demanda_agregada_profesor.csv"
    assert RUTA_DEMANDA_DEFAULT.exists()

def test_columnas_faltantes_es_error(tmp_path):
    p = tmp_path / "malo.csv"
    pd.DataFrame({"municipio": [1], "hour": [18]}).to_csv(p, index=False)
    with pytest.raises(ValueError):
        cargar_demanda(p)
