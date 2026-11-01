"""Meses de pago y frecuencia de dividendos (portfolio_engine.dividend_calendar)."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import portfolio_engine as P  # noqa: E402

REF = pd.Timestamp("2026-11-01")


def serie(fechas):
    return pd.Series([1.0] * len(fechas), index=pd.to_datetime(fechas))


def test_mensual_trimestral_semestral_anual():
    mensual = serie(pd.date_range("2024-01-01", "2026-10-01", freq="MS") + pd.Timedelta(days=14))
    assert P.dividend_calendar(mensual, REF) == (list(range(1, 13)), "Mensual")
    # Coca-Cola: la fecha ex se recorre del 1-dic al 13-mar; con la ventana de un año no aparece noviembre.
    ko = serie(["2025-06-13", "2025-09-15", "2025-12-01", "2026-03-13", "2026-06-15", "2026-09-15"])
    assert P.dividend_calendar(ko, REF) == ([3, 6, 9, 12], "Trimestral")
    assert P.dividend_calendar(serie(["2024-05-10", "2024-12-10", "2025-05-12", "2025-12-11", "2026-05-11"]), REF)[1] == "Semestral"
    # Walmex: anual, pero el último se pagó en dos exhibiciones (nov y dic): la mediana ignora la segunda.
    walmex = serie(["2023-11-27", "2024-11-11", "2025-11-18", "2025-12-16"])
    assert P.dividend_calendar(walmex, REF) == ([11, 12], "Anual")


def test_sin_pagos_recientes_y_sin_datos():
    assert P.dividend_calendar(serie(["2020-03-01", "2021-03-01"]), REF) == (None, None)
    assert P.dividend_calendar(None, REF) == (None, None)
    stats = P.dividend_stats(serie(["2025-06-13", "2025-09-15", "2025-12-01", "2026-03-13", "2026-06-15", "2026-09-15"]), REF)
    assert stats["dividend_frequency"] == "Trimestral" and stats["dividend_months"] == [3, 6, 9, 12]
