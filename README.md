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

## Estructura

| Archivo | Descripción |
|---|---|
| `portfolio_engine.py` | Motor de análisis y generación de los JSON. |
| `index.html` | Dashboard estático que consume los JSON. |
| `portfolio_data.json` | Datos crudos por instrumento (generado). |
| `daily_report.json` | Reporte diario clasificado (generado). |
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
