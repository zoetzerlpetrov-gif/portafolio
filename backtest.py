"""Backtest simple de las reglas del motor (portfolio_engine.py) con 10 años de precios diarios ajustados.

Cada 5 días hábiles, y solo con los datos disponibles hasta ese día, se calculan las mismas señales que usa el reporte
(tendencia semanal, cercanía a soporte/resistencia en ATR, doble piso/techo confirmado, media de 200 días y la
clasificación final). Después se mide qué pasó con el precio en los siguientes 21 días hábiles (~1 mes).

«Acierto»: para señales alcistas, que el precio subiera en ese mes; para bajistas, que bajara. Se compara contra
«comprar y mantener»: el rendimiento promedio a 1 mes de TODOS los días evaluados, haya señal o no.
No incluye comisiones, impuestos ni deslizamiento. Rendimientos pasados no garantizan resultados futuros.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

import portfolio_engine as P

HORIZONTE = 21
PASO = 5
INICIO = 260  # ~1 año de datos antes de la primera evaluación (media de 200 días + ventanas)

ALCISTAS = ("tendencia_alcista", "cerca_soporte", "doble_piso", "arriba_sma200", "comprar")
BAJISTAS = ("tendencia_bajista", "cerca_resistencia", "doble_techo", "abajo_sma200", "vender")
NOMBRES = {
    "tendencia_alcista": "Tendencia semanal alcista", "tendencia_bajista": "Tendencia semanal bajista",
    "cerca_soporte": "A menos de 1 ATR del soporte", "cerca_resistencia": "A menos de 1 ATR de la resistencia",
    "doble_piso": "Doble piso confirmado", "doble_techo": "Doble techo confirmado",
    "arriba_sma200": "Arriba de la media de 200 días", "abajo_sma200": "Abajo de la media de 200 días",
    "comprar": "Clasificación «comprar»", "vender": "Clasificación «vender»",
}


def senales(daily: pd.DataFrame, i: int, weekly: pd.Series, sma200: pd.Series, atr_s: pd.Series) -> dict[str, bool]:
    """Señales en el día i usando solo datos hasta ese día."""
    win = daily.iloc[: i + 1]
    fecha = win.index[-1]
    cur = float(win["Close"].iloc[-1])
    a = P.Analysis(ticker="bt", current_price=cur)
    a.trend, _ = P.weekly_trend(weekly[weekly.index <= fecha])
    a.atr_14 = float(atr_s.iloc[i]) if not np.isnan(atr_s.iloc[i]) else None
    s = sma200.iloc[i]
    a.above_sma200 = None if np.isnan(s) else bool(cur > s)
    a.support, a.resistance = P.support_resistance(win.tail(P.SR_LOOKBACK), cur)
    a.double_bottom, a.double_top = P.detect_double_touch(win.tail(P.DOUBLE_LOOKBACK + 1), atr_value=a.atr_14)
    ns, nr = P.near_levels(a)
    cat = P.classify(a)["category"]
    return {"tendencia_alcista": a.trend == "alcista", "tendencia_bajista": a.trend == "bajista",
            "cerca_soporte": ns, "cerca_resistencia": nr, "doble_piso": a.double_bottom, "doble_techo": a.double_top,
            "arriba_sma200": a.above_sma200 is True, "abajo_sma200": a.above_sma200 is False,
            "comprar": cat == "comprar", "vender": cat == "vender"}


def backtest_ticker(daily: pd.DataFrame) -> dict[str, list[float]] | None:
    daily = daily.dropna(subset=["High", "Low", "Close"])
    n = len(daily)
    if n < INICIO + HORIZONTE + 1:
        return None
    close = daily["Close"].to_numpy(float)
    weekly = daily["Close"].resample("W-FRI").last().dropna()
    sma200 = daily["Close"].rolling(P.SMA_LONG).mean()
    h, l, c = daily["High"], daily["Low"], daily["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr_s = tr.ewm(alpha=1 / P.ATR_DAYS, adjust=False).mean()
    out: dict[str, list[float]] = {k: [] for k in ALCISTAS + BAJISTAS}
    out["_todos"] = []
    for i in range(INICIO, n - HORIZONTE, PASO):
        fwd = close[i + HORIZONTE] / close[i] - 1
        out["_todos"].append(fwd)
        for k, v in senales(daily, i, weekly, sma200, atr_s).items():
            if v:
                out[k].append(fwd)
    return out


def resumen(rets: list[float], bajista: bool) -> dict:
    if not rets:
        return {"senales": 0, "acierto_pct": None, "retorno_medio_pct": None}
    r = np.asarray(rets)
    ok = (r < 0) if bajista else (r > 0)
    return {"senales": int(len(r)), "acierto_pct": round(float(ok.mean()) * 100, 1), "retorno_medio_pct": round(float(r.mean()) * 100, 2)}


def run(daily_por_ticker: dict[str, pd.DataFrame]) -> dict:
    total: dict[str, list[float]] = {k: [] for k in ALCISTAS + BAJISTAS + ("_todos",)}
    por_ticker = {}
    for t, d in daily_por_ticker.items():
        try:
            r = backtest_ticker(d)
        except Exception:  # noqa: BLE001
            r = None
        if not r:
            continue
        for k, v in r.items():
            total[k].extend(v)
        por_ticker[t] = {"base": resumen(r["_todos"], False), "comprar": resumen(r["comprar"], False), "vender": resumen(r["vender"], True)}
    base = resumen(total["_todos"], False)
    reglas = {k: {"nombre": NOMBRES[k], "tipo": "bajista" if k in BAJISTAS else "alcista", **resumen(total[k], k in BAJISTAS)}
              for k in ALCISTAS + BAJISTAS}
    return {"generated_at": datetime.now(P.MX_TZ).isoformat(), "horizonte_dias": HORIZONTE, "paso_dias": PASO, "anios": 10,
            "tickers": len(por_ticker), "comprar_y_mantener": base, "reglas": reglas, "por_ticker": por_ticker,
            "nota": "Sin comisiones, impuestos ni deslizamiento. Acierto alcista = subió en 21 días hábiles; bajista = bajó. "
                    "Comparar contra «comprar y mantener» (todos los días evaluados). Rendimientos pasados no garantizan resultados futuros. No es asesoría financiera."}
