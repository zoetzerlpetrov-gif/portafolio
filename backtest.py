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

ALCISTAS = ("tendencia_alcista", "cerca_soporte", "doble_piso", "arriba_sma200", "rsi_sobreventa", "macd_positivo", "momentum_positivo",
            "volumen_alto_al_alza", "mfi_sobreventa", "comprar_anterior", "comprar")
BAJISTAS = ("tendencia_bajista", "cerca_resistencia", "doble_techo", "abajo_sma200", "rsi_sobrecompra", "macd_negativo", "momentum_negativo",
            "volumen_alto_a_la_baja", "mfi_sobrecompra", "vender_anterior", "vender")
NOMBRES = {
    "tendencia_alcista": "Tendencia semanal alcista", "tendencia_bajista": "Tendencia semanal bajista",
    "cerca_soporte": "A menos de 1 ATR del soporte", "cerca_resistencia": "A menos de 1 ATR de la resistencia",
    "doble_piso": "Doble piso confirmado", "doble_techo": "Doble techo confirmado",
    "arriba_sma200": "Arriba de la media de 200 días", "abajo_sma200": "Abajo de la media de 200 días",
    "rsi_sobreventa": "RSI(14) menor a 30", "rsi_sobrecompra": "RSI(14) mayor a 70",
    "macd_positivo": "Histograma MACD positivo", "macd_negativo": "Histograma MACD negativo",
    "momentum_positivo": "Momentum 12-1 meses positivo", "momentum_negativo": "Momentum 12-1 meses negativo",
    "volumen_alto_al_alza": "Volumen relativo ≥ 1.5× en día de alza", "volumen_alto_a_la_baja": "Volumen relativo ≥ 1.5× en día de baja",
    "mfi_sobreventa": "MFI(14) menor a 20", "mfi_sobrecompra": "MFI(14) mayor a 80",
    "comprar_anterior": "«Comprar» sin confirmaciones (versión anterior)", "vender_anterior": "«Vender» sin confirmaciones (versión anterior)",
    "comprar": "«Comprar» con confirmaciones (RSI, momentum, volumen, 200 días)", "vender": "«Vender» con confirmaciones",
}
TRAMO_PRUEBA_ANIOS = 3  # los últimos 3 años se reservan para comprobar fuera de muestra


def _v(serie: pd.Series, i: int):
    x = serie.iloc[i]
    return None if pd.isna(x) else float(x)


def senales(daily: pd.DataFrame, i: int, weekly: pd.Series, ind: pd.DataFrame) -> dict[str, bool]:
    """Señales en el día i usando solo datos hasta ese día."""
    win = daily.iloc[: i + 1]
    fecha = win.index[-1]
    cur = float(win["Close"].iloc[-1])
    prev = float(win["Close"].iloc[-2])
    a = P.Analysis(ticker="bt", current_price=cur)
    a.trend, _ = P.weekly_trend(weekly[weekly.index <= fecha])
    a.atr_14 = _v(ind["atr"], i)
    s = _v(ind["sma200"], i)
    a.above_sma200 = None if s is None else bool(cur > s)
    a.support, a.resistance = P.support_resistance(win.tail(P.SR_LOOKBACK), cur)
    a.double_bottom, a.double_top = P.detect_double_touch(win.tail(P.DOUBLE_LOOKBACK + 1), atr_value=a.atr_14)
    ns, nr = P.near_levels(a)
    anterior = P.classify(a)["category"]  # sin RSI, momentum ni volumen (como antes de las confirmaciones)
    a.rsi_14, a.mom_12_1_pct, a.rvol = _v(ind["rsi"], i), _v(ind["mom_12_1"], i), _v(ind["rvol"], i)
    cat = P.classify(a)["category"]
    rsi, macd, mom, rvol, mfi = a.rsi_14, _v(ind["macd_hist"], i), a.mom_12_1_pct, a.rvol, _v(ind["mfi"], i)
    return {"tendencia_alcista": a.trend == "alcista", "tendencia_bajista": a.trend == "bajista",
            "cerca_soporte": ns, "cerca_resistencia": nr, "doble_piso": a.double_bottom, "doble_techo": a.double_top,
            "arriba_sma200": a.above_sma200 is True, "abajo_sma200": a.above_sma200 is False,
            "rsi_sobreventa": rsi is not None and rsi < 30, "rsi_sobrecompra": rsi is not None and rsi > 70,
            "macd_positivo": macd is not None and macd > 0, "macd_negativo": macd is not None and macd < 0,
            "momentum_positivo": mom is not None and mom > 0, "momentum_negativo": mom is not None and mom < 0,
            "volumen_alto_al_alza": rvol is not None and rvol >= 1.5 and cur > prev,
            "volumen_alto_a_la_baja": rvol is not None and rvol >= 1.5 and cur < prev,
            "mfi_sobreventa": mfi is not None and mfi < 20, "mfi_sobrecompra": mfi is not None and mfi > 80,
            "comprar_anterior": anterior == "comprar", "vender_anterior": anterior == "vender",
            "comprar": cat == "comprar", "vender": cat == "vender"}


def backtest_ticker(daily: pd.DataFrame) -> dict[str, dict[str, list[float]]] | None:
    """Rendimientos a 21 días después de cada señal, separados en tramo de aprendizaje («ent») y de prueba («prueba»)."""
    daily = daily.dropna(subset=["High", "Low", "Close"])
    n = len(daily)
    if n < INICIO + HORIZONTE + 1:
        return None
    close = daily["Close"].to_numpy(float)
    weekly = daily["Close"].resample("W-FRI").last().dropna()
    ind = P.indicator_series(daily)
    corte = daily.index[-1] - pd.DateOffset(years=TRAMO_PRUEBA_ANIOS)
    out = {t: {k: [] for k in ALCISTAS + BAJISTAS + ("_todos",)} for t in ("ent", "prueba")}
    for i in range(INICIO, n - HORIZONTE, PASO):
        tramo = "prueba" if daily.index[i] >= corte else "ent"
        fwd = close[i + HORIZONTE] / close[i] - 1
        out[tramo]["_todos"].append(fwd)
        for k, v in senales(daily, i, weekly, ind).items():
            if v:
                out[tramo][k].append(fwd)
    return out


def resumen(rets: list[float], bajista: bool) -> dict:
    if not rets:
        return {"senales": 0, "acierto_pct": None, "retorno_medio_pct": None, "retorno_mediano_pct": None}
    r = np.asarray(rets)
    ok = (r < 0) if bajista else (r > 0)
    return {"senales": int(len(r)), "acierto_pct": round(float(ok.mean()) * 100, 1), "retorno_medio_pct": round(float(r.mean()) * 100, 2),
            "retorno_mediano_pct": round(float(np.median(r)) * 100, 2)}


def run(daily_por_ticker: dict[str, pd.DataFrame], clase=None) -> dict:
    """clase(ticker) → «cripto», «etf» o «accion» para separar resultados por tipo de activo."""
    claves = ALCISTAS + BAJISTAS + ("_todos",)
    total = {t: {k: [] for k in claves} for t in ("ent", "prueba")}
    por_clase: dict[str, dict[str, list[float]]] = {}
    por_ticker = {}
    for t, d in daily_por_ticker.items():
        try:
            r = backtest_ticker(d)
        except Exception:  # noqa: BLE001
            r = None
        if not r:
            continue
        cl = clase(t) if clase else "todos"
        pc = por_clase.setdefault(cl, {k: [] for k in claves})
        for tramo in ("ent", "prueba"):
            for k, v in r[tramo].items():
                total[tramo][k].extend(v)
                pc[k].extend(v)
        todos = r["ent"]["_todos"] + r["prueba"]["_todos"]
        por_ticker[t] = {"base": resumen(todos, False), "comprar": resumen(r["ent"]["comprar"] + r["prueba"]["comprar"], False),
                         "vender": resumen(r["ent"]["vender"] + r["prueba"]["vender"], True)}

    def tabla(src):
        return {k: {"nombre": NOMBRES[k], "tipo": "bajista" if k in BAJISTAS else "alcista", **resumen(src[k], k in BAJISTAS)} for k in ALCISTAS + BAJISTAS}

    junto = {k: total["ent"][k] + total["prueba"][k] for k in claves}
    return {"generated_at": datetime.now(P.MX_TZ).isoformat(), "horizonte_dias": HORIZONTE, "paso_dias": PASO, "anios": 10,
            "tramo_prueba_anios": TRAMO_PRUEBA_ANIOS, "tickers": len(por_ticker),
            "comprar_y_mantener": resumen(junto["_todos"], False), "reglas": tabla(junto),
            "aprendizaje": {"comprar_y_mantener": resumen(total["ent"]["_todos"], False), "reglas": tabla(total["ent"])},
            "prueba": {"comprar_y_mantener": resumen(total["prueba"]["_todos"], False), "reglas": tabla(total["prueba"])},
            "por_clase": {c: {"comprar_y_mantener": resumen(v["_todos"], False), "reglas": tabla(v)} for c, v in por_clase.items()},
            "por_ticker": por_ticker,
            "nota": "Sin comisiones, impuestos ni deslizamiento. Acierto alcista = subió en 21 días hábiles; bajista = bajó. "
                    "Compara cada regla contra «comprar y mantener» (todos los días evaluados). La mediana evita que unos pocos movimientos "
                    "enormes (cripto) distorsionen el promedio. «Prueba» = últimos 3 años, que no se usaron para elegir las reglas. "
                    "Rendimientos pasados no garantizan resultados futuros. No es asesoría financiera."}
