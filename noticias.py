"""
Noticias de cada instrumento a partir de canales RSS públicos de medios financieros.

Por qué: la API de noticias de Yahoo que usaba yfinance (`Ticker.news`) responde 404 desde
octubre de 2026 y devolvía listas vacías para los ~570 instrumentos sin avisar. Las RSS
por emisora de Yahoo no sirven: su robots.txt es «Disallow: /».

Cómo funciona:
1. Lee los RSS de FUENTES, solo si su robots.txt permite leerlos (401/403 al pedir robots.txt =
   no permitido), con una pausa entre fuentes.
2. Guarda solo título, enlace, medio y fecha. Nunca el texto del artículo (derechos de autor).
   Se acumulan 14 días en noticias_cache.json, así la cobertura crece con cada corrida diaria.
3. A cada instrumento le toca un titular si su nombre (o «NYSE: XXX», «Nasdaq: XXX») aparece
   en él. Es una coincidencia por nombre: puede fallar con nombres que también son palabras
   comunes; esos solo cuentan con el formato de bolsa.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

UA = "portafolio-monitor/1.0 (+https://github.com/zoetzerlpetrov-gif/portafolio)"
CACHE = "noticias_cache.json"
DIAS = 14
MAX_POR_INSTRUMENTO = 5
PAUSA_S = 1.0

# (nombre del medio, URL del RSS). Revisadas el 01-nov-2026: su robots.txt permite leerlas.
# Descartadas por robots.txt: Yahoo Finance, CNBC, MarketWatch, Investing.com, Google News,
# Business Wire, GlobeNewswire y la SEC.
FUENTES = [
    ("El Economista", "https://www.eleconomista.com.mx/rss/ultimas-noticias"),
    ("El Financiero", "https://www.elfinanciero.com.mx/arc/outboundfeeds/rss/?outputType=xml"),
    ("Expansión", "https://expansion.mx/rss"),
    ("El CEO", "https://elceo.com/feed/"),
    ("PR Newswire", "https://www.prnewswire.com/rss/financial-services-latest-news/financial-services-latest-news-list.rss"),
    ("PR Newswire", "https://www.prnewswire.com/rss/news-releases-list.rss"),
    ("Benzinga", "https://www.benzinga.com/feed"),
]

# Nombres que también son palabras comunes (o se confunden con otra cosa): solo cuentan si el
# titular trae el formato de bolsa, p. ej. «(NYSE: V)».
AMBIGUOS = {
    "visa", "target", "gap", "ball", "block", "fox", "oro", "avalanche", "mosaic", "corning",
    "progressive", "southern", "general", "match", "apple hospitality", "unity", "snap",
    "square", "best", "amazon", "nu", "sol", "chainlink", "polygon", "stellar", "aptos",
    "sui", "near", "ondo", "pepe", "uber", "meta", "alphabet", "oracle", "intel", "american",
    "united", "delta", "first", "global", "national", "energy", "solar", "steel", "bimbo",
}
# Lo que va entre paréntesis en el nombre a veces es otra marca (FEMSA (OXXO)) y a veces solo una
# descripción que aparece en cualquier titular: esas no sirven para buscar.
DESCRIPTORES = {"the", "méxico", "mexico", "eua", "usa", "carlos slim", "oro", "plata", "cobre", "adr", "binance", "ripple"}
_SUFIJOS = re.compile(
    r",?\s+(inc\.?|incorporated|corporation|corp\.?|company|co\.?|ltd\.?|limited|plc|n\.?v\.?|s\.?a\.?b?\.?"
    r"( de c\.?v\.?)?|s\.?a\.?|ag|se|holdings?|group|the|class [a-c])$",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------- descarga
def permitido_por_robots(url: str) -> bool:
    p = urlsplit(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        req = urllib.request.Request(f"{p.scheme}://{p.netloc}/robots.txt", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            rp.parse(r.read().decode("utf-8", "replace").splitlines())
    except urllib.error.HTTPError as e:
        return e.code not in (401, 403)  # 401/403: el sitio no deja leer; otro error: sin reglas
    except Exception:  # noqa: BLE001  sin red para robots.txt: no hay reglas que leer
        return True
    return rp.can_fetch(UA, url)


def _fecha(txt: str | None) -> str | None:
    if not txt:
        return None
    try:
        d = parsedate_to_datetime(txt.strip())
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(txt.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).isoformat()


def leer_rss(datos: bytes, medio: str) -> list[dict]:
    """RSS 2.0 o Atom → [{title, link, publisher, date}] (sin descripción ni texto del artículo)."""
    try:
        raiz = ET.fromstring(datos)
    except ET.ParseError:
        return []
    out = []
    for it in raiz.iter():
        tag = it.tag.rsplit("}", 1)[-1]
        if tag not in ("item", "entry"):
            continue
        hijo = {c.tag.rsplit("}", 1)[-1]: c for c in it}
        titulo = (hijo.get("title").text or "").strip() if hijo.get("title") is not None else ""
        enlace = hijo.get("link")
        link = (enlace.text or enlace.get("href") or "").strip() if enlace is not None else ""
        fecha = next((hijo[k].text for k in ("pubDate", "published", "updated", "date") if hijo.get(k) is not None), None)
        if titulo and link.startswith("http"):
            out.append({"title": re.sub(r"\s+", " ", titulo), "link": link, "publisher": medio, "date": _fecha(fecha)})
    return out


def descargar(fuentes=FUENTES, pausa=PAUSA_S, bajar=None, permitido=permitido_por_robots) -> tuple[list[dict], dict]:
    """Titulares de todas las fuentes permitidas y un estado por fuente (para el log y la auditoría)."""
    if bajar is None:
        def bajar(url):
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=25) as r:
                return r.read()
    items, estado = [], {}
    for medio, url in fuentes:
        if not permitido(url):
            estado[url] = "robots.txt no lo permite"
            continue
        try:
            nuevos = leer_rss(bajar(url), medio)
            items += nuevos
            estado[url] = f"{len(nuevos)} titulares"
        except Exception as e:  # noqa: BLE001  una fuente caída no detiene las demás
            estado[url] = f"error: {type(e).__name__}"
        time.sleep(pausa)
    return items, estado


def acumular(nuevos: list[dict], previos: list[dict], ahora: datetime | None = None, dias: int = DIAS) -> list[dict]:
    """Une, quita repetidos por enlace y deja solo los últimos `dias` días (lo más nuevo primero)."""
    ahora = ahora or datetime.now(timezone.utc)
    limite = (ahora - timedelta(days=dias)).isoformat()
    vistos, out = set(), []
    for n in sorted(nuevos + previos, key=lambda x: x.get("date") or "", reverse=True):
        if n["link"] in vistos or (n.get("date") or ahora.isoformat()) < limite:
            continue
        vistos.add(n["link"])
        out.append(n)
    return out


# --------------------------------------------------------------------------- coincidencias
def alias(ticker: str, nombre: str | None, sector: str | None = "") -> tuple[list[str], list[str]]:
    """(nombres que deben aparecer tal cual con mayúsculas, claves de bolsa) de un instrumento."""
    if (sector or "").lower().startswith("etf"):
        return [], []
    nombres = []
    bruto = (nombre or "").strip()
    if len(bruto) >= 30:  # yfinance corta los nombres largos a ~31 caracteres: se quita la última palabra
        bruto = bruto.rsplit(" ", 1)[0]
    entre_par = [x for x in re.findall(r"\((.*?)\)", bruto) if x.strip().lower() not in DESCRIPTORES]
    partes = [re.sub(r"\(.*?\)", "", bruto)] + entre_par
    for p in partes:
        p = p.strip(" ,.")
        for _ in range(3):
            p = _SUFIJOS.sub("", p).strip(" ,.")
        if len(p) >= 3 and p[0].isupper() and p.lower() not in AMBIGUOS:
            nombres.append(p)
    base = ticker.split(".")[0].split("-")[0]
    claves = [base] if base.isalpha() and not ticker.endswith("-USD") else []
    if ticker.endswith(".MX") and len(base) >= 5 and base.lower() not in AMBIGUOS:
        nombres.append(base.capitalize())  # Walmex, Femsa, Gmexico…
    return list(dict.fromkeys(nombres)), claves


def _patron(nombres: list[str], claves: list[str]) -> re.Pattern | None:
    alts = [r"(?<![\w])" + re.escape(n) + r"(?![\w])" for n in nombres]
    alts += [r"\b(?:NYSE|Nasdaq|NASDAQ|NYSE American|BMV|TSX|LSE)\s*:\s*" + re.escape(c) + r"\b" for c in claves]
    return re.compile("|".join(alts)) if alts else None


def asignar(instrumentos: list, titulares: list[dict], ruido=None, limite: int = MAX_POR_INSTRUMENTO) -> int:
    """Pone en `.news` de cada instrumento sus titulares (lo más nuevo primero). Devuelve cuántos tienen alguno."""
    con = 0
    for a in instrumentos:
        nombres, claves = alias(a.ticker, getattr(a, "name", None), getattr(a, "sector", ""))
        pat = _patron(nombres, claves)
        if pat is None:
            a.news = []
            continue
        a.news = [n for n in titulares if pat.search(n["title"]) and not (ruido and ruido(n["title"]))][:limite]
        con += bool(a.news)
    return con


def actualizar(instrumentos: list, ruido=None, ruta: str = CACHE, **kw) -> dict:
    """Descarga, acumula en la caché y asigna. Devuelve un resumen para el reporte diario."""
    try:
        previos = json.load(open(ruta, encoding="utf-8")).get("items", [])
    except (OSError, ValueError):
        previos = []
    nuevos, estado = descargar(**kw)
    todos = acumular(nuevos, previos)
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump({"actualizado": datetime.now(timezone.utc).isoformat(), "fuentes": estado, "items": todos},
                  fh, ensure_ascii=False, indent=0)
    con = asignar(instrumentos, todos, ruido=ruido)
    return {"titulares_nuevos": len(nuevos), "titulares_14_dias": len(todos), "instrumentos_con_noticias": con,
            "fuentes": estado}
