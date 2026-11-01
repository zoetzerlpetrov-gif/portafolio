"""Noticias por instrumento desde RSS (noticias.py). Correr: python3 -m pytest -q tests"""
import os
import sys
import types
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import noticias as N  # noqa: E402

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Megacable aumenta 30% sus ganancias</title><link>https://ejemplo.mx/1</link><pubDate>Fri, 31 Oct 2026 14:00:00 GMT</pubDate>
<description>texto que no se guarda</description></item>
<item><title>Hamilton gana el GP de M\xc3\xa9xico</title><link>https://ejemplo.mx/2</link><pubDate>Fri, 31 Oct 2026 13:00:00 GMT</pubDate></item>
<item><title>Baker Hughes Announces Results (NYSE: KR)</title><link>https://ejemplo.mx/3</link><pubDate>Fri, 31 Oct 2026 12:00:00 GMT</pubDate></item>
</channel></rss>"""


def inst(ticker, name, sector=""):
    return types.SimpleNamespace(ticker=ticker, name=name, sector=sector, news=[])


def test_leer_rss_solo_titulo_enlace_medio_y_fecha():
    items = N.leer_rss(RSS, "Expansión")
    assert len(items) == 3 and set(items[0]) == {"title", "link", "publisher", "date"}
    assert items[0]["date"] == "2026-10-31T14:00:00+00:00" and items[0]["publisher"] == "Expansión"


def test_alias_sin_descriptores_ni_sufijos():
    assert N.alias("MOS", "Mosaic Company (The)") == ([], ["MOS"])               # ambiguo: solo «NYSE: MOS»
    assert N.alias("VLRS", "Volaris (México)")[0] == ["Volaris"]                 # «México» no sirve para buscar
    assert N.alias("FEMSAUBD.MX", "FEMSA (OXXO)")[0] == ["FEMSA", "OXXO", "Femsaubd"]
    assert N.alias("EXPD", "Expeditors International of Was")[0] == ["Expeditors International of"]
    assert N.alias("VOO", "Vanguard S&P 500", "ETFs / Índices") == ([], [])
    assert N.alias("SOL-USD", "Solana")[1] == []


def test_asignar_por_nombre_y_por_clave_de_bolsa():
    a = [inst("MEGACPO.MX", "Megacable"), inst("VLRS", "Volaris (México)"), inst("KR", "Kroger Company (The)"), inst("RACE", "Ferrari")]
    assert N.asignar(a, N.leer_rss(RSS, "X")) == 2
    assert a[0].news[0]["link"] == "https://ejemplo.mx/1" and a[1].news == [] and a[2].news[0]["link"] == "https://ejemplo.mx/3"


def test_acumular_sin_repetidos_y_14_dias():
    ahora = datetime(2026, 11, 1, tzinfo=timezone.utc)
    viejo = {"title": "x", "link": "https://v", "publisher": "X", "date": "2026-10-01T00:00:00+00:00"}
    nuevos = N.leer_rss(RSS, "X")
    todos = N.acumular(nuevos, nuevos[:1] + [viejo], ahora)
    assert len(todos) == 3 and all(t["link"] != "https://v" for t in todos)


def test_fuente_bloqueada_por_robots_se_omite_y_una_caida_no_detiene():
    def bajar(url):
        if "caida" in url:
            raise OSError("sin red")
        return RSS
    items, estado = N.descargar([("A", "https://a/rss"), ("B", "https://caida/rss"), ("C", "https://bloq/rss")], pausa=0,
                                bajar=bajar, permitido=lambda u: "bloq" not in u)
    assert len(items) == 3 and estado["https://caida/rss"].startswith("error") and "robots" in estado["https://bloq/rss"]
