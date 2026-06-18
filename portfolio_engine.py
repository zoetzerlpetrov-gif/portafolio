"""
Motor de análisis de portafolio de inversión.

Recibe una lista de tickers (formato Yahoo Finance, p.ej. "FUNO11.MX",
"WALMEX.MX", "AAPL", "VOO") y para cada uno calcula:

  - Precios máximo y mínimo de 10 años, 5 años, 1 año, y precio actual.
  - Serie diaria de los últimos 12 meses (para el gráfico miniatura / sparkline).
  - Tendencia (alcista / bajista / lateral) según regresión sobre las
    últimas 9 velas semanales.
  - Próximo soporte y resistencia según los pivotes de los últimos 60 días.
  - Información de dividendos: si reparte, último pagado y próxima fecha
    ex-dividendo si Yahoo la tiene disponible.
  - Detección de doble piso / doble techo (doble toque).

Luego `build_report()` puntúa cada instrumento y lo clasifica en
"comprar", "vender" o "esperar". TODO es decisión de apoyo, no asesoría.

Dependencias: yfinance, pandas, numpy
Uso:           python3 portfolio_engine.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf


# --------------------------------------------------------------------------- #
# Configuración: edita aquí tu lista (hasta 100 instrumentos).
# --------------------------------------------------------------------------- #
WATCHLIST = [
    # --- ETFs núcleo ---
    "VOO",            # S&P 500
    "QQQ",            # Nasdaq-100

    # --- FIBRAs mexicanas ---
    "FUNO11.MX",      # Fibra Uno (diversificada)
    "FIBRAPL14.MX",   # Fibra Prologis (industrial, la más grande)
    "DANHOS13.MX",    # Fibra Danhos (comercial/mixto)
    "FMTY14.MX",      # Fibra Mty (diversificada)
    "FIBRAMQ12.MX",   # Fibra Macquarie (industrial)

    # --- Criptomonedas ---
    "BTC-USD", "XRP-USD", "XLM-USD", "HBAR-USD",

    # --- Tecnología ---
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",

    # --- Semiconductores ---
    "NVDA", "TSM", "AVGO", "ASML", "AMD",

    # --- Energía ---
    "XOM", "CVX", "SHEL", "TTE", "NEE",

    # --- Automotriz ---
    "TSLA", "TM", "VWAGY", "GM", "BYDDY",

    # --- Aviación y aeroespacial ---
    "BA", "EADSY", "GE", "DAL", "VLRS",

    # --- Salud ---
    "UNH", "ABT", "MDT", "TMO", "ISRG",

    # --- Farmacéuticas ---
    "LLY", "NVO", "JNJ", "MRK", "ABBV",

    # --- Defensa / militar ---
    "LMT", "RTX", "NOC", "GD", "LHX",

    # --- Consumo / retail ---
    "WMT", "KO", "WALMEX.MX", "KOF", "COST",

    # --- Finanzas / bancos ---
    "JPM", "V", "MA", "BRK-B", "GFNORTEO.MX",
]

# Umbrales (ajústalos a tu gusto).
TREND_PCT_PER_WEEK = 0.5   # % por semana para considerar tendencia, no lateral
NEAR_LEVEL_PCT = 3.0       # qué tan cerca (%) de soporte/resistencia cuenta
PIVOT_ORDER = 3            # velas a cada lado para confirmar un pivote
DOUBLE_TOUCH_TOL = 1.5     # tolerancia (%) para considerar dos toques "iguales"


# --------------------------------------------------------------------------- #
# Estructura del resultado por instrumento.
# --------------------------------------------------------------------------- #
@dataclass
class Analysis:
    ticker: str
    ok: bool = True
    error: str | None = None

    current_price: float | None = None
    currency: str | None = None

    high_10y: float | None = None
    low_10y: float | None = None
    high_5y: float | None = None
    low_5y: float | None = None
    high_1y: float | None = None
    low_1y: float | None = None

    trend: str | None = None              # "alcista" | "bajista" | "lateral"
    trend_pct_per_week: float | None = None

    support: float | None = None
    resistance: float | None = None
    dist_to_support_pct: float | None = None
    dist_to_resistance_pct: float | None = None

    double_bottom: bool = False
    double_top: bool = False

    pays_dividend: bool = False
    last_dividend: float | None = None
    last_dividend_date: str | None = None
    dividend_yield_pct: float | None = None
    next_ex_dividend_date: str | None = None

    sparkline_12m: list[float] = field(default_factory=list)  # cierres diarios


# --------------------------------------------------------------------------- #
# Cálculos puros (no tocan la red — fáciles de probar con datos sintéticos).
# --------------------------------------------------------------------------- #
def price_extremes(daily: pd.DataFrame, years: int) -> tuple[float, float]:
    """Máximo (de High) y mínimo (de Low) en la ventana de `years` años."""
    cutoff = daily.index[-1] - pd.DateOffset(years=years)
    window = daily[daily.index >= cutoff]
    return float(window["High"].max()), float(window["Low"].min())


def weekly_trend(weekly_close: pd.Series,
                 threshold: float = TREND_PCT_PER_WEEK) -> tuple[str, float]:
    """Tendencia con regresión lineal sobre las últimas 9 velas semanales."""
    closes = weekly_close.dropna().values[-9:]
    if len(closes) < 3:
        return "indeterminada", 0.0
    x = np.arange(len(closes))
    slope = np.polyfit(x, closes, 1)[0]          # pendiente (precio por semana)
    pct = slope / closes.mean() * 100.0          # normalizada a %
    if pct > threshold:
        return "alcista", float(pct)
    if pct < -threshold:
        return "bajista", float(pct)
    return "lateral", float(pct)


def find_pivots(values: np.ndarray, order: int = PIVOT_ORDER
                ) -> tuple[list[int], list[int]]:
    """Índices de máximos y mínimos locales (pivotes) confirmados."""
    highs, lows = [], []
    n = len(values)
    for i in range(order, n - order):
        window = values[i - order: i + order + 1]
        if values[i] == window.max():
            highs.append(i)
        if values[i] == window.min():
            lows.append(i)
    return highs, lows


def support_resistance(daily: pd.DataFrame, current: float,
                       lookback: int = 60) -> tuple[float, float]:
    """Soporte y resistencia más cercanos según pivotes de los últimos N días."""
    recent = daily.tail(lookback)
    high_pivots, _ = find_pivots(recent["High"].values)
    _, low_pivots = find_pivots(recent["Low"].values)

    res_levels = [recent["High"].values[i] for i in high_pivots
                  if recent["High"].values[i] > current]
    sup_levels = [recent["Low"].values[i] for i in low_pivots
                  if recent["Low"].values[i] < current]

    # Si no hay pivote por encima/debajo, usamos el extremo de la ventana.
    resistance = float(min(res_levels)) if res_levels else float(recent["High"].max())
    support = float(max(sup_levels)) if sup_levels else float(recent["Low"].min())
    return support, resistance


def detect_double_touch(daily: pd.DataFrame, lookback: int = 60,
                        tol: float = DOUBLE_TOUCH_TOL) -> tuple[bool, bool]:
    """Doble piso (dos mínimos a la par) y doble techo (dos máximos a la par)."""
    recent = daily.tail(lookback)
    high_pivots, _ = find_pivots(recent["High"].values)
    _, low_pivots = find_pivots(recent["Low"].values)

    def has_pair(idxs: list[int], series: np.ndarray) -> bool:
        levels = sorted(series[i] for i in idxs)
        for a, b in zip(levels, levels[1:]):
            if a > 0 and abs(b - a) / a * 100 <= tol:
                return True
        return False

    double_top = has_pair(high_pivots, recent["High"].values)
    double_bottom = has_pair(low_pivots, recent["Low"].values)
    return double_bottom, double_top


# --------------------------------------------------------------------------- #
# Acceso a datos (sí toca la red — usa yfinance).
# --------------------------------------------------------------------------- #
def analyze_ticker(ticker: str) -> Analysis:
    res = Analysis(ticker=ticker)
    try:
        tk = yf.Ticker(ticker)

        daily = tk.history(period="10y", interval="1d", auto_adjust=False)
        if daily.empty:
            res.ok = False
            res.error = "Sin datos diarios (¿ticker inválido?)"
            return res
        daily = daily.dropna(subset=["High", "Low", "Close"])

        current = float(daily["Close"].iloc[-1])
        res.current_price = current

        res.high_10y, res.low_10y = price_extremes(daily, 10)
        res.high_5y, res.low_5y = price_extremes(daily, 5)
        res.high_1y, res.low_1y = price_extremes(daily, 1)

        # Sparkline: cierres diarios de los últimos 12 meses.
        cutoff = daily.index[-1] - pd.DateOffset(years=1)
        res.sparkline_12m = [round(v, 4) for v in
                             daily[daily.index >= cutoff]["Close"].tolist()]

        # Tendencia semanal (9 velas).
        weekly = tk.history(period="6mo", interval="1wk", auto_adjust=False)
        res.trend, res.trend_pct_per_week = weekly_trend(weekly["Close"])

        # Soporte / resistencia (60 días).
        res.support, res.resistance = support_resistance(daily, current)
        res.dist_to_support_pct = round((current - res.support) / current * 100, 2)
        res.dist_to_resistance_pct = round((res.resistance - current) / current * 100, 2)

        # Doble toque.
        res.double_bottom, res.double_top = detect_double_touch(daily)

        # Dividendos.
        _fill_dividends(tk, res)

        res.currency = _safe_info(tk, "currency")
        return res

    except Exception as exc:  # noqa: BLE001
        res.ok = False
        res.error = f"{type(exc).__name__}: {exc}"
        return res


def _fill_dividends(tk: yf.Ticker, res: Analysis) -> None:
    """Rellena la info de dividendos de forma defensiva (Yahoo es inconsistente)."""
    try:
        divs = tk.dividends
        if divs is not None and len(divs) > 0:
            res.pays_dividend = True
            res.last_dividend = float(divs.iloc[-1])
            res.last_dividend_date = divs.index[-1].date().isoformat()
    except Exception:
        pass

    # Rendimiento y próxima fecha ex-dividendo (no siempre disponible en FIBRAs).
    y = _safe_info(tk, "dividendYield")
    if y is not None:
        # yfinance a veces lo da como fracción (0.04) y a veces como % (4.0).
        res.dividend_yield_pct = round(y * 100, 2) if y < 1 else round(y, 2)

    ex = _safe_info(tk, "exDividendDate")
    if ex:
        try:
            res.next_ex_dividend_date = datetime.fromtimestamp(
                ex, tz=timezone.utc).date().isoformat()
        except (TypeError, ValueError, OSError):
            res.next_ex_dividend_date = str(ex)


def _safe_info(tk: yf.Ticker, key: str):
    try:
        return tk.info.get(key)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Reporte: puntúa y clasifica. Señales de apoyo, NO asesoría financiera.
# --------------------------------------------------------------------------- #
def classify(a: Analysis) -> dict:
    reasons: list[str] = []
    near_support = (a.dist_to_support_pct is not None
                    and a.dist_to_support_pct <= NEAR_LEVEL_PCT)
    near_resistance = (a.dist_to_resistance_pct is not None
                       and a.dist_to_resistance_pct <= NEAR_LEVEL_PCT)

    score = 0
    if a.trend == "alcista":
        score += 1; reasons.append("Tendencia semanal alcista")
    elif a.trend == "bajista":
        score -= 1; reasons.append("Tendencia semanal bajista")

    if near_support:
        score += 1; reasons.append(f"Precio cerca del soporte ({a.dist_to_support_pct}%)")
    if near_resistance:
        score -= 1; reasons.append(f"Precio cerca de la resistencia ({a.dist_to_resistance_pct}%)")
    if a.double_bottom:
        score += 1; reasons.append("Doble piso detectado")
    if a.double_top:
        score -= 1; reasons.append("Doble techo detectado")

    if score >= 2:
        category = "comprar"
    elif score <= -2:
        category = "vender"
    else:
        category = "esperar"

    return {"category": category, "score": score, "reasons": reasons}


def build_report(results: list[Analysis]) -> dict:
    buckets = {"comprar": [], "vender": [], "esperar": [], "error": []}
    for a in results:
        if not a.ok:
            buckets["error"].append({"ticker": a.ticker, "error": a.error})
            continue
        c = classify(a)
        buckets[c["category"]].append({
            "ticker": a.ticker,
            "price": a.current_price,
            "trend": a.trend,
            "support": a.support,
            "resistance": a.resistance,
            "score": c["score"],
            "reasons": c["reasons"],
        })
    for k in ("comprar", "vender", "esperar"):
        buckets[k].sort(key=lambda x: x["score"], reverse=(k != "vender"))
    return {"generated_at": datetime.now(timezone.utc).isoformat(),
            "report": buckets}


# --------------------------------------------------------------------------- #
def main() -> None:
    results = [analyze_ticker(t) for t in WATCHLIST]

    # Guarda el detalle completo (lo que tu base de datos / frontend consumiría).
    with open("portfolio_data.json", "w", encoding="utf-8") as fh:
        json.dump([asdict(a) for a in results], fh, ensure_ascii=False, indent=2)

    report = build_report(results)
    with open("daily_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    # Resumen legible en consola.
    print(f"Reporte {report['generated_at']}\n")
    for cat in ("comprar", "vender", "esperar"):
        print(f"== {cat.upper()} ==")
        for item in report["report"][cat]:
            print(f"  {item['ticker']:<16} ${item['price']:<10} "
                  f"score={item['score']:+d}  {', '.join(item['reasons'])}")
        print()
    if report["report"]["error"]:
        print("== ERRORES ==")
        for e in report["report"]["error"]:
            print(f"  {e['ticker']}: {e['error']}")


if __name__ == "__main__":
    main()
