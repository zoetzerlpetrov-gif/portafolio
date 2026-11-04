"""Volumen relativo con la sesión de hoy a medias: se usa el último día completo."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import portfolio_engine as P  # noqa: E402

IDX = pd.date_range("2026-10-26", "2026-11-04", freq="B", tz="America/New_York")
DF = pd.DataFrame({"Close": range(len(IDX))}, index=IDX)


def test_sesion_de_hoy_abierta_y_cerrada():
    abierta = pd.Timestamp("2026-11-04 17:35", tz="UTC")   # 12:35 en Nueva York
    cerrada = pd.Timestamp("2026-11-04 22:00", tz="UTC")   # 17:00 en Nueva York
    assert P.sesion_incompleta(DF, "KO", abierta) is True
    assert P.sesion_incompleta(DF, "KO", cerrada) is False
    assert P.sesion_incompleta(DF, "BTC-USD", cerrada) is True  # cripto: el día de hoy nunca está completo
    assert P.sesion_incompleta(DF, "KO", pd.Timestamp("2026-11-05 14:00", tz="UTC")) is False  # la última barra ya es de ayer
