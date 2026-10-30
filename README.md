# Portafolio · Panel diario

Panel web que cada día calcula señales técnicas de apoyo a la decisión para una
lista de instrumentos (ETFs, FIBRAS, criptomonedas, acciones por sector) y las
publica en un dashboard estático.

> **Aviso:** las señales son apoyo a la decisión, **no asesoría financiera**.

## ¿Cómo funciona?

1. `portfolio_engine.py` descarga datos de Yahoo Finance (vía `yfinance`) para
   cada ticker de la `WATCHLIST`, calcula máximos/mínimos, tendencia semanal,
   soporte/resistencia, doble toque y liquidez, y los clasifica en
   **comprar / esperar / vender**.
2. El motor guarda dos archivos: `portfolio_data.json` (datos completos) y
   `daily_report.json` (reporte clasificado, con `generated_at` en hora de
   Ciudad de México).
3. `index.html` lee esos JSON y los muestra como panel.
4. Un workflow de GitHub Actions ejecuta el motor a diario y publica vía GitHub Pages.

## Reglas de las señales (revisadas el 30-oct-2026)

- Precios **ajustados** por splits y dividendos (`auto_adjust=True`).
- **Soporte/resistencia:** pivotes de 60 días. Si el precio ya rompió todos los niveles, ese lado queda vacío (no se inventa un nivel).
- **«Cerca de»:** a menos de 1 ATR(14), así se adapta a la volatilidad de cada activo.
- **Doble piso/techo:** dos toques a menos de 1.5 % entre sí, separados ≥ 10 días hábiles, con rebote (o caída) ≥ 3 ATR entre ellos y el precio ya por encima (o debajo) de la línea de cuello. El segundo toque debe ser de los últimos 30 días.
- **Filtro de tendencia:** «comprar» solo si el precio está arriba de su media de 200 días, con RSI < 70, momentum 12-1 positivo y volumen relativo ≥ 1.
- **Rebote:** RSI(14) < 30 con el precio arriba de su media de 200 días (la señal con más acierto en el backtest, también en los últimos 3 años).
- **Precaución** (antes «vender»): en el backtest el precio subió más veces de las que bajó tras esta señal; es una alerta, no una predicción.
- **Dividendo:** rendimiento de 12 meses calculado con los dividendos pagados y el precio actual.
- **Backtest** (`backtest.py` → `backtest.json`): cada regla evaluada cada 5 días hábiles durante 10 años, con el rendimiento a 21 días contra «comprar y mantener». Sin comisiones ni impuestos.

## Estructura

| Archivo | Descripción |
|---|---|
| `portfolio_engine.py` | Motor de análisis y generación de los JSON. |
| `index.html` | Dashboard estático que consume los JSON. |
| `portfolio_data.json` | Datos crudos por instrumento (generado). |
| `daily_report.json` | Reporte diario clasificado (generado). |
| `backtest.py` / `backtest.json` | Backtest de las reglas a 10 años (generado). |
| `requirements.txt` | Dependencias de Python. |
| `.github/workflows/dailymain.yml` | Automatización diaria (cron + commit). |

## Ejecutar localmente

```bash
pip install -r requirements.txt
python3 portfolio_engine.py        # genera los JSON
python3 -m http.server 8000        # luego abre http://localhost:8000
```

## Automatización

El workflow corre todos los días (cron `23 9 * * *` UTC ≈ 03:23 CDMX) y también
puede dispararse a mano desde la pestaña **Actions** con *Run workflow*. Tras
calcular, hace commit de los JSON actualizados y GitHub Pages republica el panel.

## Personalizar

- **Instrumentos:** edita la lista `WATCHLIST` y el diccionario `META` en `portfolio_engine.py`.
- **Umbrales:** ajusta las constantes (`TREND_PCT_PER_WEEK`, `NEAR_LEVEL_PCT`,
  `SLEEP_BETWEEN`, `MAX_RETRIES`, etc.) en ese mismo archivo.
