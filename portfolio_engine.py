"""
Motor de análisis de portafolio de inversión.

Para cada ticker (formato Yahoo Finance) calcula: máx/mín de 10/5/1 años y
precio actual, serie diaria de 12 meses (sparkline), tendencia semanal,
soporte/resistencia, dividendos y doble toque. `build_report()` lo clasifica
en comprar/vender/esperar. TODO es decisión de apoyo, no asesoría.

Moneda: cada instrumento trae su divisa (USD, MXN, EUR…). Los .MX cotizan en
MXN; los de EE.UU. y la mayoría de los ADRs en USD.

Dependencias: yfinance, pandas, numpy
"""

from __future__ import annotations

import json
import re; import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta

# Zona horaria de Ciudad de México (UTC-6, fijo, sin horario de verano).
# Se usa para sellar 'generated_at' en hora local en lugar de UTC.
MX_TZ = timezone(timedelta(hours=-6))
import numpy as np
import pandas as pd
import yfinance as yf


# --------------------------------------------------------------------------- #
# Lista de instrumentos a monitorear. Comentario: nombre — moneda típica.
# El encabezado de cada bloque indica el sector / giro.
# --------------------------------------------------------------------------- #
WATCHLIST = [
    # ===== ETFs / ÍNDICES (núcleo) =====
    "VOO",            # Vanguard S&P 500 — USD
    "QQQ",            # Invesco Nasdaq-100 — USD
    "VTI",            # Vanguard Total US Market — USD
    "DIA",            # Dow Jones 30 — USD
    "IWM",            # Russell 2000 (small caps) — USD
    "VEA",            # Mercados desarrollados ex-EE.UU. — USD
    "VWO",            # Mercados emergentes — USD
    "VT",             # Acciones de todo el mundo — USD
    "SCHD",           # Dividendos EE.UU. (calidad) — USD
    "NAFTRACISHRS.MX",# IPC México (BMV) — MXN

    # ===== FIBRAS (bienes raíces México) =====
    "FUNO11.MX",      # Fibra Uno (diversificada) — MXN
    "FIBRAPL14.MX",   # Fibra Prologis (industrial) — MXN
    "DANHOS13.MX",    # Fibra Danhos (comercial/mixto) — MXN
    "FMTY14.MX",      # Fibra Mty (diversificada) — MXN
    "FIBRAMQ12.MX",   # Fibra Macquarie (industrial) — MXN
    "FNOVA17.MX",     # Fibra Nova (industrial norte/bajío) — MXN
    "FIHO12.MX",      # Fibra Hotel (hotelera) — MXN
    "FSHOP13.MX",     # Fibra Shop (centros comerciales) — MXN
    "FINN13.MX",      # Fibra Inn (hotelera) — MXN
    "STORAGE18.MX",   # Fibra Storage (autoalmacenamiento) — MXN

    # ===== CRIPTOMONEDAS =====
    "BTC-USD",        # Bitcoin — USD
    "ETH-USD",        # Ethereum — USD
    "XRP-USD",        # XRP (Ripple) — USD
    "XLM-USD",        # Stellar Lumens — USD
    "HBAR-USD",       # Hedera — USD
    "SOL-USD",        # Solana — USD
    "ADA-USD",        # Cardano — USD
    "BNB-USD",        # BNB (Binance) — USD
    "DOGE-USD",       # Dogecoin — USD
    "AVAX-USD",       # Avalanche — USD

    # ===== TECNOLOGÍA / SOFTWARE =====
    "AAPL",           # Apple — USD
    "MSFT",           # Microsoft — USD
    "GOOGL",          # Alphabet (Google) — USD
    "AMZN",           # Amazon — USD
    "META",           # Meta (Facebook) — USD
    "ORCL",           # Oracle — USD
    "CRM",            # Salesforce — USD
    "ADBE",           # Adobe — USD
    "SAP",            # SAP (ADR) — USD
    "IBM",            # IBM — USD

    # ===== SEMICONDUCTORES =====
    "NVDA",           # Nvidia — USD
    "TSM",            # TSMC (ADR) — USD
    "AVGO",           # Broadcom — USD
    "ASML",           # ASML (ADR) — USD
    "AMD",            # AMD — USD
    "QCOM",           # Qualcomm — USD
    "INTC",           # Intel — USD
    "TXN",            # Texas Instruments — USD
    "MU",             # Micron — USD
    "AMAT",           # Applied Materials — USD

    # ===== ENERGÍA (petróleo y gas) =====
    "XOM",            # ExxonMobil — USD
    "CVX",            # Chevron — USD
    "SHEL",           # Shell (ADR) — USD
    "TTE",            # TotalEnergies (ADR) — USD
    "BP",             # BP (ADR) — USD
    "COP",            # ConocoPhillips — USD
    "PBR",            # Petrobras (ADR) — USD
    "ENB",            # Enbridge — USD
    "SLB",            # Schlumberger — USD
    "EOG",            # EOG Resources — USD

    # ===== ENERGÍA RENOVABLE / UTILITIES =====
    "NEE",            # NextEra Energy — USD
    "FSLR",           # First Solar — USD
    "ENPH",           # Enphase Energy — USD
    "BEP",            # Brookfield Renewable — USD
    "DUK",            # Duke Energy — USD
    "SO",             # Southern Company — USD
    "AEP",            # American Electric Power — USD
    "D",              # Dominion Energy — USD
    "EXC",            # Exelon — USD
    "IBDRY",          # Iberdrola (ADR) — USD

    # ===== AUTOMOTRIZ =====
    "TSLA",           # Tesla — USD
    "TM",             # Toyota (ADR) — USD
    "VWAGY",          # Volkswagen (ADR) — USD
    "GM",             # General Motors — USD
    "F",              # Ford — USD
    "STLA",           # Stellantis — USD
    "HMC",            # Honda (ADR) — USD
    "BYDDY",          # BYD (ADR) — USD
    "MBGYY",          # Mercedes-Benz (ADR) — USD
    "RACE",           # Ferrari — USD

    # ===== AVIACIÓN / AEROLÍNEAS =====
    "DAL",            # Delta Air Lines — USD
    "UAL",            # United Airlines — USD
    "AAL",            # American Airlines — USD
    "LUV",            # Southwest Airlines — USD
    "RYAAY",          # Ryanair (ADR) — USD
    "VLRS",           # Volaris (México, ADR) — USD
    "CPA",            # Copa Airlines (Panamá) — USD
    "JBLU",           # JetBlue — USD
    "ALK",            # Alaska Air — USD
    "DLAKY",          # Lufthansa (ADR) — USD
    "AERO.MX",        # Grupo Aeroméxico — MXN
    "AC.TO",          # Air Canada — CAD

    # ===== AEROESPACIAL Y DEFENSA / MILITAR =====
    "BA",             # Boeing — USD
    "LMT",            # Lockheed Martin — USD
    "RTX",            # RTX / Raytheon — USD
    "NOC",            # Northrop Grumman — USD
    "GD",             # General Dynamics — USD
    "LHX",            # L3Harris — USD
    "GE",             # GE Aerospace — USD
    "EADSY",          # Airbus (ADR) — USD
    "HWM",            # Howmet Aerospace — USD
    "TDG",            # TransDigm — USD
    "SPCX",            # SpaceX (Space Exploration Tech) - USD

    # ===== TURISMO / HOSPITALIDAD =====
    "MAR",            # Marriott International — USD
    "HLT",            # Hilton Worldwide — USD
    "BKNG",           # Booking Holdings — USD

    # ===== SALUD / DISPOSITIVOS MÉDICOS =====
    "UNH",            # UnitedHealth — USD
    "ABT",            # Abbott Laboratories — USD
    "MDT",            # Medtronic — USD
    "TMO",            # Thermo Fisher — USD
    "DHR",            # Danaher — USD
    "ISRG",           # Intuitive Surgical — USD
    "SYK",            # Stryker — USD
    "BSX",            # Boston Scientific — USD
    "BDX",            # Becton Dickinson — USD
    "EW",             # Edwards Lifesciences — USD

    # ===== FARMACÉUTICAS =====
    "LLY",            # Eli Lilly — USD
    "NVO",            # Novo Nordisk (ADR) — USD
    "JNJ",            # Johnson & Johnson — USD
    "MRK",            # Merck — USD
    "ABBV",           # AbbVie — USD
    "PFE",            # Pfizer — USD
    "RHHBY",          # Roche (ADR) — USD
    "NVS",            # Novartis (ADR) — USD
    "AZN",            # AstraZeneca (ADR) — USD
    "AMGN",           # Amgen — USD

    # ===== BIOTECNOLOGÍA =====
    "REGN",           # Regeneron — USD
    "VRTX",           # Vertex Pharmaceuticals — USD
    "GILD",           # Gilead Sciences — USD
    "BIIB",           # Biogen — USD
    "MRNA",           # Moderna — USD
    "BNTX",           # BioNTech (ADR) — USD
    "ALNY",           # Alnylam — USD
    "INCY",           # Incyte — USD
    "NBIX",           # Neurocrine — USD
    "ILMN",           # Illumina — USD

    # ===== ALIMENTOS =====
    "NSRGY",          # Nestlé (ADR) — USD
    "MDLZ",           # Mondelez — USD
    "GIS",            # General Mills — USD
    "KHC",            # Kraft Heinz — USD
    "HSY",            # Hershey — USD
    "TSN",            # Tyson Foods — USD
    "CAG",            # Conagra — USD
    "HRL",            # Hormel — USD
    "GRUMAB.MX",      # Gruma (Maseca) — MXN
    "BIMBOA.MX",      # Grupo Bimbo — MXN

    # ===== BEBIDAS =====
    "KO",             # Coca-Cola — USD
    "PEP",            # PepsiCo — USD
    "KOF",            # Coca-Cola FEMSA (ADR) — USD
    "FMX",            # FEMSA (ADR) — USD
    "MNST",           # Monster Beverage — USD
    "KDP",            # Keurig Dr Pepper — USD
    "STZ",            # Constellation Brands — USD
    "BUD",            # AB InBev (ADR) — USD
    "DEO",            # Diageo (ADR) — USD
    "TAP",            # Molson Coors — USD

    # ===== RESTAURANTES / COMIDA RÁPIDA =====
    "MCD",            # McDonald's — USD
    "SBUX",           # Starbucks — USD
    "CMG",            # Chipotle — USD
    "YUM",            # Yum! Brands (KFC, Pizza Hut) — USD
    "QSR",            # Restaurant Brands (Burger King) — USD
    "DRI",            # Darden (Olive Garden) — USD
    "DPZ",            # Domino's Pizza — USD
    "WEN",            # Wendy's — USD
    "TXRH",           # Texas Roadhouse — USD
    "ALSEA.MX",       # Alsea (Starbucks/Domino's México) — MXN

    # ===== CONSUMO BÁSICO / HOGAR =====
    "PG",             # Procter & Gamble — USD
    "UL",             # Unilever (ADR) — USD
    "CL",             # Colgate-Palmolive — USD
    "KMB",            # Kimberly-Clark — USD
    "CHD",            # Church & Dwight — USD
    "CLX",            # Clorox — USD
    "EL",             # Estée Lauder — USD
    "KVUE",           # Kenvue — USD
    "KIMBERA.MX",     # Kimberly-Clark de México — MXN
    "COTY",           # Coty — USD

    # ===== RETAIL / COMERCIO =====
    "WMT",            # Walmart — USD
    "COST",           # Costco — USD
    "HD",             # Home Depot — USD
    "LOW",            # Lowe's — USD
    "TGT",            # Target — USD
    "DG",             # Dollar General — USD
    "ORLY",           # O'Reilly Automotive — USD
    "WALMEX.MX",      # Walmart de México — MXN
    "CHDRAUIB.MX",    # Chedraui — MXN
    "LIVEPOLC-1.MX",  # El Puerto de Liverpool — MXN

    # ===== FINANZAS / BANCOS =====
    "JPM",            # JPMorgan Chase — USD
    "BAC",            # Bank of America — USD
    "WFC",            # Wells Fargo — USD
    "C",              # Citigroup — USD
    "GS",             # Goldman Sachs — USD
    "MS",             # Morgan Stanley — USD
    "SAN",            # Banco Santander (ADR) — USD
    "BBVA",           # BBVA (ADR) — USD
    "GFNORTEO.MX",    # Grupo Financiero Banorte — MXN
    "BBAJIOO.MX",     # Banco del Bajío — MXN
    "GENTERA.MX",     # Gentera (microfinanzas) — MXN

    # ===== SEGUROS =====
    "BRK-B",          # Berkshire Hathaway — USD
    "CB",             # Chubb Limited — USD

    # ===== PAGOS / FINTECH =====
    "V",              # Visa — USD
    "MA",             # Mastercard — USD
    "PYPL",           # PayPal — USD
    "AXP",            # American Express — USD
    "COIN",           # Coinbase — USD
    "FI",             # Fiserv — USD
    "GPN",            # Global Payments — USD
    "SOFI",           # SoFi — USD
    "NU",             # Nu Holdings (Nubank) — USD
    "XYZ",            # Block (antes SQ) — USD

    # ===== TELECOMUNICACIONES =====
    "T",              # AT&T — USD
    "VZ",             # Verizon — USD
    "TMUS",           # T-Mobile US — USD
    "CMCSA",          # Comcast — USD
    "CHTR",           # Charter Communications — USD
    "AMXB.MX",        # América Móvil — MXN
    "TEF",            # Telefónica (ADR) — USD
    "VOD",            # Vodafone (ADR) — USD
    "ORAN",           # Orange (ADR) — USD
    "TU",             # Telus — USD

    # ===== MEDIOS / ENTRETENIMIENTO =====
    "NFLX",           # Netflix — USD
    "DIS",            # Walt Disney — USD
    "WBD",            # Warner Bros. Discovery — USD
    "PSKY",           # Paramount — USD
    "SPOT",           # Spotify — USD
    "RBLX",           # Roblox — USD
    "EA",             # Electronic Arts — USD
    "TTWO",           # Take-Two Interactive — USD
    "LYV",            # Live Nation — USD
    "FOXA",           # Fox Corporation — USD

    # ===== E-COMMERCE / INTERNET =====
    "MELI",           # MercadoLibre — USD
    "BABA",           # Alibaba (ADR) — USD
    "PDD",            # PDD / Temu (ADR) — USD
    "SE",             # Sea Limited (ADR) — USD
    "SHOP",           # Shopify — USD
    "EBAY",           # eBay — USD
    "ETSY",           # Etsy — USD
    "JD",             # JD.com (ADR) — USD
    "CPNG",           # Coupang — USD
    "ABNB",           # Airbnb — USD

    # ===== INDUSTRIAL / MAQUINARIA =====
    "CAT",            # Caterpillar — USD
    "DE",             # John Deere — USD
    "HON",            # Honeywell — USD
    "MMM",            # 3M — USD
    "EMR",            # Emerson Electric — USD
    "ETN",            # Eaton — USD
    "ITW",            # Illinois Tool Works — USD
    "PH",             # Parker Hannifin — USD
    "ROK",            # Rockwell Automation — USD
    "CMI",            # Cummins — USD

    # ===== CONSTRUCCIÓN / MATERIALES =====
    "CEMEXCPO.MX",    # Cemex (cemento) — MXN
    "MLM",            # Martin Marietta — USD
    "VMC",            # Vulcan Materials — USD
    "NUE",            # Nucor (acero) — USD
    "DHI",            # D.R. Horton (vivienda) — USD
    "LEN",            # Lennar (vivienda) — USD
    "ORBIA.MX",       # Orbia (químicos/infra) — MXN
    "GCARSOA1.MX",    # Grupo Carso — MXN
    "MAS",            # Masco — USD
    "BLDR",           # Builders FirstSource — USD
    "VINTE.MX",       # Vinte Viviendas Integrales — MXN
    "CADUA.MX",       # Corpovael / Cadu Inmobiliaria — MXN

    # ===== MINERÍA / METALES / ORO =====
    "NEM",            # Newmont (oro) — USD
    "GOLD",           # Barrick Gold — USD
    "FCX",            # Freeport-McMoRan (cobre) — USD
    "SCCO",           # Southern Copper — USD
    "AEM",            # Agnico Eagle (oro) — USD
    "RIO",            # Rio Tinto (ADR) — USD
    "BHP",            # BHP (ADR) — USD
    "VALE",           # Vale (ADR) — USD
    "GMEXICOB.MX",    # Grupo México (minería) — MXN
    "WPM",            # Wheaton Precious Metals — USD
]

import dividendos as DIV  # noqa: E402  listas de acciones con dividendo (EUA y México)

# Tabla de nombre y sector por ticker (para mostrarlos en el dashboard).
META = {
    # ETFs / Índices
    "VOO": ("Vanguard S&P 500", "ETFs / Índices"),
    "QQQ": ("Invesco Nasdaq-100", "ETFs / Índices"),
    "VTI": ("Vanguard Total US Market", "ETFs / Índices"),
    "DIA": ("Dow Jones 30", "ETFs / Índices"),
    "IWM": ("Russell 2000 (small caps)", "ETFs / Índices"),
    "VEA": ("Desarrollados ex-EE.UU.", "ETFs / Índices"),
    "VWO": ("Mercados emergentes", "ETFs / Índices"),
    "VT": ("Acciones mundiales", "ETFs / Índices"),
    "SCHD": ("Dividendos EE.UU.", "ETFs / Índices"),
    "NAFTRACISHRS.MX": ("IPC México", "ETFs / Índices"),
    # FIBRAs
    "FUNO11.MX": ("Fibra Uno", "FIBRAs (bienes raíces)"),
    "FIBRAPL14.MX": ("Fibra Prologis", "FIBRAs (bienes raíces)"),
    "DANHOS13.MX": ("Fibra Danhos", "FIBRAs (bienes raíces)"),
    "FMTY14.MX": ("Fibra Mty", "FIBRAs (bienes raíces)"),
    "FIBRAMQ12.MX": ("Fibra Macquarie", "FIBRAs (bienes raíces)"),
    "FNOVA17.MX": ("Fibra Nova", "FIBRAs (bienes raíces)"),
    "FIHO12.MX": ("Fibra Hotel", "FIBRAs (bienes raíces)"),
    "FSHOP13.MX": ("Fibra Shop", "FIBRAs (bienes raíces)"),
    "FINN13.MX": ("Fibra Inn", "FIBRAs (bienes raíces)"),
    "STORAGE18.MX": ("Fibra Storage", "FIBRAs (bienes raíces)"),
    # Criptomonedas
    "BTC-USD": ("Bitcoin", "Criptomonedas"),
    "ETH-USD": ("Ethereum", "Criptomonedas"),
    "XRP-USD": ("XRP (Ripple)", "Criptomonedas"),
    "XLM-USD": ("Stellar Lumens", "Criptomonedas"),
    "HBAR-USD": ("Hedera", "Criptomonedas"),
    "SOL-USD": ("Solana", "Criptomonedas"),
    "ADA-USD": ("Cardano", "Criptomonedas"),
    "BNB-USD": ("BNB (Binance)", "Criptomonedas"),
    "DOGE-USD": ("Dogecoin", "Criptomonedas"),
    "AVAX-USD": ("Avalanche", "Criptomonedas"),
    # Tecnología / Software
    "AAPL": ("Apple", "Tecnología / Software"),
    "MSFT": ("Microsoft", "Tecnología / Software"),
    "GOOGL": ("Alphabet (Google)", "Tecnología / Software"),
    "AMZN": ("Amazon", "Tecnología / Software"),
    "META": ("Meta (Facebook)", "Tecnología / Software"),
    "ORCL": ("Oracle", "Tecnología / Software"),
    "CRM": ("Salesforce", "Tecnología / Software"),
    "ADBE": ("Adobe", "Tecnología / Software"),
    "SAP": ("SAP", "Tecnología / Software"),
    "IBM": ("IBM", "Tecnología / Software"),
    # Semiconductores
    "NVDA": ("Nvidia", "Semiconductores"),
    "TSM": ("TSMC", "Semiconductores"),
    "AVGO": ("Broadcom", "Semiconductores"),
    "ASML": ("ASML", "Semiconductores"),
    "AMD": ("AMD", "Semiconductores"),
    "QCOM": ("Qualcomm", "Semiconductores"),
    "INTC": ("Intel", "Semiconductores"),
    "TXN": ("Texas Instruments", "Semiconductores"),
    "MU": ("Micron", "Semiconductores"),
    "AMAT": ("Applied Materials", "Semiconductores"),
    # Energía (petróleo y gas)
    "XOM": ("ExxonMobil", "Energía (petróleo y gas)"),
    "CVX": ("Chevron", "Energía (petróleo y gas)"),
    "SHEL": ("Shell", "Energía (petróleo y gas)"),
    "TTE": ("TotalEnergies", "Energía (petróleo y gas)"),
    "BP": ("BP", "Energía (petróleo y gas)"),
    "COP": ("ConocoPhillips", "Energía (petróleo y gas)"),
    "PBR": ("Petrobras", "Energía (petróleo y gas)"),
    "ENB": ("Enbridge", "Energía (petróleo y gas)"),
    "SLB": ("Schlumberger", "Energía (petróleo y gas)"),
    "EOG": ("EOG Resources", "Energía (petróleo y gas)"),
    # Energía renovable / Utilities
    "NEE": ("NextEra Energy", "Energía renovable / Utilities"),
    "FSLR": ("First Solar", "Energía renovable / Utilities"),
    "ENPH": ("Enphase Energy", "Energía renovable / Utilities"),
    "BEP": ("Brookfield Renewable", "Energía renovable / Utilities"),
    "DUK": ("Duke Energy", "Energía renovable / Utilities"),
    "SO": ("Southern Company", "Energía renovable / Utilities"),
    "AEP": ("American Electric Power", "Energía renovable / Utilities"),
    "D": ("Dominion Energy", "Energía renovable / Utilities"),
    "EXC": ("Exelon", "Energía renovable / Utilities"),
    "IBDRY": ("Iberdrola", "Energía renovable / Utilities"),
    # Automotriz
    "TSLA": ("Tesla", "Automotriz"),
    "TM": ("Toyota", "Automotriz"),
    "VWAGY": ("Volkswagen", "Automotriz"),
    "GM": ("General Motors", "Automotriz"),
    "F": ("Ford", "Automotriz"),
    "STLA": ("Stellantis", "Automotriz"),
    "HMC": ("Honda", "Automotriz"),
    "BYDDY": ("BYD", "Automotriz"),
    "MBGYY": ("Mercedes-Benz", "Automotriz"),
    "RACE": ("Ferrari", "Automotriz"),
    # Aviación / Aerolíneas
    "DAL": ("Delta Air Lines", "Aviación / Aerolíneas"),
    "UAL": ("United Airlines", "Aviación / Aerolíneas"),
    "AAL": ("American Airlines", "Aviación / Aerolíneas"),
    "LUV": ("Southwest Airlines", "Aviación / Aerolíneas"),
    "RYAAY": ("Ryanair", "Aviación / Aerolíneas"),
    "VLRS": ("Volaris (México)", "Aviación / Aerolíneas"),
    "CPA": ("Copa Airlines", "Aviación / Aerolíneas"),
    "JBLU": ("JetBlue", "Aviación / Aerolíneas"),
    "ALK": ("Alaska Air", "Aviación / Aerolíneas"),
    "DLAKY": ("Lufthansa", "Aviación / Aerolíneas"),
    "AERO.MX": ("Grupo Aeroméxico", "Aviación / Aerolíneas"),
    "AC.TO": ("Air Canada", "Aviación / Aerolíneas"),
    # Aeroespacial y Defensa / Militar
    "BA": ("Boeing", "Aeroespacial y Defensa"),
    "LMT": ("Lockheed Martin", "Aeroespacial y Defensa"),
    "RTX": ("RTX / Raytheon", "Aeroespacial y Defensa"),
    "NOC": ("Northrop Grumman", "Aeroespacial y Defensa"),
    "GD": ("General Dynamics", "Aeroespacial y Defensa"),
    "LHX": ("L3Harris", "Aeroespacial y Defensa"),
    "GE": ("GE Aerospace", "Aeroespacial y Defensa"),
    "EADSY": ("Airbus", "Aeroespacial y Defensa"),
    "HWM": ("Howmet Aerospace", "Aeroespacial y Defensa"),
    "TDG": ("TransDigm", "Aeroespacial y Defensa"),
    "SPCX": ("SpaceX", "Aeroespacial y Defensa"),
    # Turismo / Hospitalidad
    "MAR": ("Marriott International", "Turismo / Hospitalidad"),
    "HLT": ("Hilton Worldwide", "Turismo / Hospitalidad"),
    "BKNG": ("Booking Holdings", "Turismo / Hospitalidad"),
    # Salud / Dispositivos médicos
    "UNH": ("UnitedHealth", "Salud / Dispositivos médicos"),
    "ABT": ("Abbott Laboratories", "Salud / Dispositivos médicos"),
    "MDT": ("Medtronic", "Salud / Dispositivos médicos"),
    "TMO": ("Thermo Fisher", "Salud / Dispositivos médicos"),
    "DHR": ("Danaher", "Salud / Dispositivos médicos"),
    "ISRG": ("Intuitive Surgical", "Salud / Dispositivos médicos"),
    "SYK": ("Stryker", "Salud / Dispositivos médicos"),
    "BSX": ("Boston Scientific", "Salud / Dispositivos médicos"),
    "BDX": ("Becton Dickinson", "Salud / Dispositivos médicos"),
    "EW": ("Edwards Lifesciences", "Salud / Dispositivos médicos"),
    # Farmacéuticas
    "LLY": ("Eli Lilly", "Farmacéuticas"),
    "NVO": ("Novo Nordisk", "Farmacéuticas"),
    "JNJ": ("Johnson & Johnson", "Farmacéuticas"),
    "MRK": ("Merck", "Farmacéuticas"),
    "ABBV": ("AbbVie", "Farmacéuticas"),
    "PFE": ("Pfizer", "Farmacéuticas"),
    "RHHBY": ("Roche", "Farmacéuticas"),
    "NVS": ("Novartis", "Farmacéuticas"),
    "AZN": ("AstraZeneca", "Farmacéuticas"),
    "AMGN": ("Amgen", "Farmacéuticas"),
    # Biotecnología
    "REGN": ("Regeneron", "Biotecnología"),
    "VRTX": ("Vertex Pharmaceuticals", "Biotecnología"),
    "GILD": ("Gilead Sciences", "Biotecnología"),
    "BIIB": ("Biogen", "Biotecnología"),
    "MRNA": ("Moderna", "Biotecnología"),
    "BNTX": ("BioNTech", "Biotecnología"),
    "ALNY": ("Alnylam", "Biotecnología"),
    "INCY": ("Incyte", "Biotecnología"),
    "NBIX": ("Neurocrine", "Biotecnología"),
    "ILMN": ("Illumina", "Biotecnología"),
    # Alimentos
    "NSRGY": ("Nestlé", "Alimentos"),
    "MDLZ": ("Mondelez", "Alimentos"),
    "GIS": ("General Mills", "Alimentos"),
    "KHC": ("Kraft Heinz", "Alimentos"),
    "HSY": ("Hershey", "Alimentos"),
    "TSN": ("Tyson Foods", "Alimentos"),
    "CAG": ("Conagra", "Alimentos"),
    "HRL": ("Hormel", "Alimentos"),
    "GRUMAB.MX": ("Gruma (Maseca)", "Alimentos"),
    "BIMBOA.MX": ("Grupo Bimbo", "Alimentos"),
    # Bebidas
    "KO": ("Coca-Cola", "Bebidas"),
    "PEP": ("PepsiCo", "Bebidas"),
    "KOF": ("Coca-Cola FEMSA", "Bebidas"),
    "FMX": ("FEMSA", "Bebidas"),
    "MNST": ("Monster Beverage", "Bebidas"),
    "KDP": ("Keurig Dr Pepper", "Bebidas"),
    "STZ": ("Constellation Brands", "Bebidas"),
    "BUD": ("AB InBev", "Bebidas"),
    "DEO": ("Diageo", "Bebidas"),
    "TAP": ("Molson Coors", "Bebidas"),
    # Restaurantes / Comida rápida
    "MCD": ("McDonald's", "Restaurantes / Comida rápida"),
    "SBUX": ("Starbucks", "Restaurantes / Comida rápida"),
    "CMG": ("Chipotle", "Restaurantes / Comida rápida"),
    "YUM": ("Yum! Brands", "Restaurantes / Comida rápida"),
    "QSR": ("Restaurant Brands", "Restaurantes / Comida rápida"),
    "DRI": ("Darden", "Restaurantes / Comida rápida"),
    "DPZ": ("Domino's Pizza", "Restaurantes / Comida rápida"),
    "WEN": ("Wendy's", "Restaurantes / Comida rápida"),
    "TXRH": ("Texas Roadhouse", "Restaurantes / Comida rápida"),
    "ALSEA.MX": ("Alsea (México)", "Restaurantes / Comida rápida"),
    # Consumo básico / Hogar
    "PG": ("Procter & Gamble", "Consumo básico / Hogar"),
    "UL": ("Unilever", "Consumo básico / Hogar"),
    "CL": ("Colgate-Palmolive", "Consumo básico / Hogar"),
    "KMB": ("Kimberly-Clark", "Consumo básico / Hogar"),
    "CHD": ("Church & Dwight", "Consumo básico / Hogar"),
    "CLX": ("Clorox", "Consumo básico / Hogar"),
    "EL": ("Estée Lauder", "Consumo básico / Hogar"),
    "KVUE": ("Kenvue", "Consumo básico / Hogar"),
    "KIMBERA.MX": ("Kimberly-Clark México", "Consumo básico / Hogar"),
    "COTY": ("Coty", "Consumo básico / Hogar"),
    # Retail / Comercio
    "WMT": ("Walmart", "Retail / Comercio"),
    "COST": ("Costco", "Retail / Comercio"),
    "HD": ("Home Depot", "Retail / Comercio"),
    "LOW": ("Lowe's", "Retail / Comercio"),
    "TGT": ("Target", "Retail / Comercio"),
    "DG": ("Dollar General", "Retail / Comercio"),
    "ORLY": ("O'Reilly Automotive", "Retail / Comercio"),
    "WALMEX.MX": ("Walmart de México", "Retail / Comercio"),
    "CHDRAUIB.MX": ("Chedraui", "Retail / Comercio"),
    "LIVEPOLC-1.MX": ("El Puerto de Liverpool", "Retail / Comercio"),
    # Finanzas / Bancos
    "JPM": ("JPMorgan Chase", "Finanzas / Bancos"),
    "BAC": ("Bank of America", "Finanzas / Bancos"),
    "WFC": ("Wells Fargo", "Finanzas / Bancos"),
    "C": ("Citigroup", "Finanzas / Bancos"),
    "GS": ("Goldman Sachs", "Finanzas / Bancos"),
    "MS": ("Morgan Stanley", "Finanzas / Bancos"),
    "SAN": ("Banco Santander", "Finanzas / Bancos"),
    "BBVA": ("BBVA", "Finanzas / Bancos"),
    "GFNORTEO.MX": ("Banorte", "Finanzas / Bancos"),
    "BBAJIOO.MX": ("Banco del Bajío", "Finanzas / Bancos"),
    "GENTERA.MX": ("Gentera", "Finanzas / Bancos"),
    # Seguros
    "BRK-B": ("Berkshire Hathaway", "Seguros"),
    "CB": ("Chubb Limited", "Seguros"),
    # Pagos / Fintech
    "V": ("Visa", "Pagos / Fintech"),
    "MA": ("Mastercard", "Pagos / Fintech"),
    "PYPL": ("PayPal", "Pagos / Fintech"),
    "AXP": ("American Express", "Pagos / Fintech"),
    "COIN": ("Coinbase", "Pagos / Fintech"),
    "FI": ("Fiserv", "Pagos / Fintech"),
    "GPN": ("Global Payments", "Pagos / Fintech"),
    "SOFI": ("SoFi", "Pagos / Fintech"),
    "NU": ("Nu Holdings (Nubank)", "Pagos / Fintech"),
    "XYZ": ("Block (antes SQ)", "Pagos / Fintech"),
    # Telecomunicaciones
    "T": ("AT&T", "Telecomunicaciones"),
    "VZ": ("Verizon", "Telecomunicaciones"),
    "TMUS": ("T-Mobile US", "Telecomunicaciones"),
    "CMCSA": ("Comcast", "Telecomunicaciones"),
    "CHTR": ("Charter Communications", "Telecomunicaciones"),
    "AMXB.MX": ("América Móvil", "Telecomunicaciones"),
    "TEF": ("Telefónica", "Telecomunicaciones"),
    "VOD": ("Vodafone", "Telecomunicaciones"),
    "ORAN": ("Orange", "Telecomunicaciones"),
    "TU": ("Telus", "Telecomunicaciones"),
    # Medios / Entretenimiento
    "NFLX": ("Netflix", "Medios / Entretenimiento"),
    "DIS": ("Walt Disney", "Medios / Entretenimiento"),
    "WBD": ("Warner Bros. Discovery", "Medios / Entretenimiento"),
    "PSKY": ("Paramount Skydance", "Medios / Entretenimiento"),
    "SPOT": ("Spotify", "Medios / Entretenimiento"),
    "RBLX": ("Roblox", "Medios / Entretenimiento"),
    "EA": ("Electronic Arts", "Medios / Entretenimiento"),
    "TTWO": ("Take-Two Interactive", "Medios / Entretenimiento"),
    "LYV": ("Live Nation", "Medios / Entretenimiento"),
    "FOXA": ("Fox Corporation", "Medios / Entretenimiento"),
    # E-commerce / Internet
    "MELI": ("MercadoLibre", "E-commerce / Internet"),
    "BABA": ("Alibaba", "E-commerce / Internet"),
    "PDD": ("PDD / Temu", "E-commerce / Internet"),
    "SE": ("Sea Limited", "E-commerce / Internet"),
    "SHOP": ("Shopify", "E-commerce / Internet"),
    "EBAY": ("eBay", "E-commerce / Internet"),
    "ETSY": ("Etsy", "E-commerce / Internet"),
    "JD": ("JD.com", "E-commerce / Internet"),
    "CPNG": ("Coupang", "E-commerce / Internet"),
    "ABNB": ("Airbnb", "E-commerce / Internet"),
    # Industrial / Maquinaria
    "CAT": ("Caterpillar", "Industrial / Maquinaria"),
    "DE": ("John Deere", "Industrial / Maquinaria"),
    "HON": ("Honeywell", "Industrial / Maquinaria"),
    "MMM": ("3M", "Industrial / Maquinaria"),
    "EMR": ("Emerson Electric", "Industrial / Maquinaria"),
    "ETN": ("Eaton", "Industrial / Maquinaria"),
    "ITW": ("Illinois Tool Works", "Industrial / Maquinaria"),
    "PH": ("Parker Hannifin", "Industrial / Maquinaria"),
    "ROK": ("Rockwell Automation", "Industrial / Maquinaria"),
    "CMI": ("Cummins", "Industrial / Maquinaria"),
    # Construcción / Materiales
    "CEMEXCPO.MX": ("Cemex", "Construcción / Materiales"),
    "MLM": ("Martin Marietta", "Construcción / Materiales"),
    "VMC": ("Vulcan Materials", "Construcción / Materiales"),
    "NUE": ("Nucor (acero)", "Construcción / Materiales"),
    "DHI": ("D.R. Horton", "Construcción / Materiales"),
    "LEN": ("Lennar", "Construcción / Materiales"),
    "ORBIA.MX": ("Orbia", "Construcción / Materiales"),
    "GCARSOA1.MX": ("Grupo Carso", "Construcción / Materiales"),
    "MAS": ("Masco", "Construcción / Materiales"),
    "BLDR": ("Builders FirstSource", "Construcción / Materiales"),
    "VINTE.MX": ("Vinte Viviendas Integrales", "Construcción / Materiales"),
    "CADUA.MX": ("Corpovael (Cadu Inmobiliaria)", "Construcción / Materiales"),
    # Minería / Metales / Oro
    "NEM": ("Newmont (oro)", "Minería / Metales"),
    "GOLD": ("Barrick Gold", "Minería / Metales"),
    "FCX": ("Freeport-McMoRan", "Minería / Metales"),
    "SCCO": ("Southern Copper", "Minería / Metales"),
    "AEM": ("Agnico Eagle", "Minería / Metales"),
    "RIO": ("Rio Tinto", "Minería / Metales"),
    "BHP": ("BHP", "Minería / Metales"),
    "VALE": ("Vale", "Minería / Metales"),
    "GMEXICOB.MX": ("Grupo México", "Minería / Metales"),
    "WPM": ("Wheaton Precious Metals", "Minería / Metales"),
}

for _t, _n, _s in DIV.DIV_MX + DIV.DIV_SLIM_EUA:
    META.setdefault(_t, (_n, _s))

# Grupo de dividendos de cada ticker (pestaña «Dividendos»).
DIV_GROUP = {**{t: "sp500" for t in DIV.DIV_SP500}, **{t: "mx" for t, _, _ in DIV.DIV_MX}, **{t: "slim_eua" for t, _, _ in DIV.DIV_SLIM_EUA}}
# Lista total sin repetidos, en orden: primero la WATCHLIST original.
ALL_TICKERS = list(dict.fromkeys(WATCHLIST + DIV.DIV_SP500 + [t for t, _, _ in DIV.DIV_MX + DIV.DIV_SLIM_EUA]))

# Umbrales (ajústalos a tu gusto).
TREND_PCT_PER_WEEK = 0.5   # % por semana para considerar tendencia, no lateral
NEAR_ATR = 1.0             # «cerca» de soporte/resistencia = a menos de 1 ATR(14) (se adapta a la volatilidad de cada activo)
ATR_DAYS = 14              # días del ATR (Wilder, 1978)
SMA_LONG = 200             # media móvil larga: «comprar» solo si el precio está arriba (filtro de tendencia)
PIVOT_ORDER = 3            # velas a cada lado para confirmar un pivote
SR_LOOKBACK = 60           # días para soportes y resistencias
DOUBLE_LOOKBACK = 120      # días para buscar doble piso/techo
DOUBLE_TOUCH_TOL = 1.5     # tolerancia (%) para considerar dos toques "iguales"
DOUBLE_MIN_GAP = 10        # días hábiles mínimos entre los dos toques
DOUBLE_MIN_SWING_ATR = 3.0 # rebote (o caída) entre los dos toques: al menos 3 ATR
DOUBLE_MAX_AGE = 30        # el segundo toque debe ser de los últimos 30 días hábiles
RSI_DAYS = 14              # RSI de Wilder; sobrecompra > 70, sobreventa < 30
RVOL_DAYS = 20             # volumen relativo: volumen de hoy / promedio de los 20 días anteriores
RVOL_MIN = 1.0             # confirmación por volumen: el día de la señal con volumen al menos igual al promedio
SLEEP_BETWEEN   = 0.35         # pausa (seg) entre tickers para no saturar a Yahoo (~570 instrumentos)
MAX_RETRIES     = 2            # reintentos por ticker si Yahoo falla/limita
LIQ_HIGH_USD    = 10_000_000   # valor operado/día (USD) para liquidez "alta"
LIQ_MED_USD     = 1_000_000    # umbral para liquidez "media" (abajo = "baja")

# --------------------------------------------------------------------------- #
@dataclass
class Analysis:
    ticker: str
    ok: bool = True
    error: str | None = None
    current_price: float | None = None
    currency: str | None = None
    price_mxn: float | None = None  # precio actual convertido a MXN (para filtros)
    name: str | None = None
    sector: str | None = None
    high_10y: float | None = None
    low_10y: float | None = None
    high_5y: float | None = None
    low_5y: float | None = None
    high_1y: float | None = None
    low_1y: float | None = None
    trend: str | None = None
    trend_pct_per_week: float | None = None
    support: float | None = None
    resistance: float | None = None
    dist_to_support_pct: float | None = None
    dist_to_resistance_pct: float | None = None
    double_bottom: bool = False      # confirmado: el precio ya rompió la línea de cuello
    double_top: bool = False
    atr_14: float | None = None
    # Indicadores internos (no se dibujan; se usan para confirmar señales y en el backtest)
    rsi_14: float | None = None
    macd_hist: float | None = None
    adx_14: float | None = None
    bb_pctb: float | None = None
    rvol: float | None = None
    obv_slope_pct: float | None = None
    mfi_14: float | None = None
    mom_12_1_pct: float | None = None
    dist_52w_high_pct: float | None = None
    # Dividendos calculados con lo realmente pagado
    dividend_group: str | None = None
    dividend_12m: float | None = None
    dividend_growth_5y_pct: float | None = None
    dividend_cagr_5y_pct: float | None = None
    dividend_years: int | None = None
    dividend_payments_last_year: int | None = None
    sma_200: float | None = None
    above_sma200: bool | None = None
    pays_dividend: bool = False
    last_dividend: float | None = None
    last_dividend_date: str | None = None
    dividend_yield_pct: float | None = None
    next_ex_dividend_date: str | None = None
    avg_volume_30d: float | None = None
    avg_value_30d_usd: float | None = None   # valor operado/día normalizado a USD
    liquidity: str | None = None             # "alta" | "media" | "baja" | "sin dato"
    sparkline_12m: list[float] = field(default_factory=list)
    news: list[dict] = field(default_factory=list)  # noticias recientes (título, liga, fuente, fecha)


# --------------------------------------------------------------------------- #
# Cálculos puros.
# --------------------------------------------------------------------------- #
def price_extremes(daily: pd.DataFrame, years: int) -> tuple[float, float]:
    cutoff = daily.index[-1] - pd.DateOffset(years=years)
    window = daily[daily.index >= cutoff]
    return float(window["High"].max()), float(window["Low"].min())


def weekly_trend(weekly_close: pd.Series,
                 threshold: float = TREND_PCT_PER_WEEK) -> tuple[str, float]:
    closes = weekly_close.dropna().values[-9:]
    if len(closes) < 3:
        return "indeterminada", 0.0
    x = np.arange(len(closes))
    slope = np.polyfit(x, closes, 1)[0]
    pct = slope / closes.mean() * 100.0
    if pct > threshold:
        return "alcista", float(pct)
    if pct < -threshold:
        return "bajista", float(pct)
    return "lateral", float(pct)


def find_pivots(values: np.ndarray, order: int = PIVOT_ORDER
                ) -> tuple[list[int], list[int]]:
    """Índices donde el valor es el máximo (o mínimo) de su ventana de ±order velas (vectorizado)."""
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n < 2 * order + 1:
        return [], []
    win = np.lib.stride_tricks.sliding_window_view(values, 2 * order + 1)
    mid = values[order:n - order]
    highs = (np.nonzero(mid == win.max(axis=1))[0] + order).tolist()
    lows = (np.nonzero(mid == win.min(axis=1))[0] + order).tolist()
    return highs, lows


def support_resistance(daily: pd.DataFrame, current: float,
                       lookback: int = SR_LOOKBACK) -> tuple[float | None, float | None]:
    """Soporte = pivote bajo más alto por debajo del precio; resistencia = pivote alto más bajo por encima.

    Si el precio ya está arriba de todos los pivotes altos (rompimiento) o abajo de todos los bajos (desplome),
    ese nivel no existe y se devuelve None: antes se usaba el máximo o mínimo del periodo, que quedaba pegado al
    precio y daba señales al revés (p. ej. «cerca del soporte» en plena caída).
    """
    recent = daily.tail(lookback)
    high_pivots, _ = find_pivots(recent["High"].values)
    _, low_pivots = find_pivots(recent["Low"].values)
    res_levels = [recent["High"].values[i] for i in high_pivots
                  if recent["High"].values[i] > current]
    sup_levels = [recent["Low"].values[i] for i in low_pivots
                  if recent["Low"].values[i] < current]
    resistance = float(min(res_levels)) if res_levels else None
    support = float(max(sup_levels)) if sup_levels else None
    return support, resistance


def atr(daily: pd.DataFrame, days: int = ATR_DAYS) -> float | None:
    """Average True Range de Wilder: rango diario promedio, contando huecos de apertura."""
    if len(daily) < days + 1:
        return None
    h, l, c = daily["High"], daily["Low"], daily["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return float(tr.ewm(alpha=1 / days, adjust=False).mean().iloc[-1])


def sma(close: pd.Series, days: int = SMA_LONG) -> float | None:
    close = close.dropna()
    return float(close.tail(days).mean()) if len(close) >= days else None


def indicator_series(daily: pd.DataFrame) -> pd.DataFrame:
    """Series diarias de todos los indicadores internos (vectorizado; el backtest las reutiliza día por día)."""
    h, l, c = daily["High"], daily["Low"], daily["Close"]
    v = daily["Volume"] if "Volume" in daily else pd.Series(np.nan, index=daily.index)
    out = pd.DataFrame(index=daily.index)
    d = c.diff()
    gain = d.clip(lower=0).ewm(alpha=1 / RSI_DAYS, adjust=False).mean()
    loss = (-d.clip(upper=0)).ewm(alpha=1 / RSI_DAYS, adjust=False).mean()
    out["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    out["macd_hist"] = macd - macd.ewm(span=9, adjust=False).mean()
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr_s = tr.ewm(alpha=1 / ATR_DAYS, adjust=False).mean()
    out["atr"] = atr_s
    up, dn = h.diff(), -l.diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=daily.index)
    ndm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=daily.index)
    pdi = 100 * pdm.ewm(alpha=1 / 14, adjust=False).mean() / atr_s
    ndi = 100 * ndm.ewm(alpha=1 / 14, adjust=False).mean() / atr_s
    out["adx"] = (100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)).ewm(alpha=1 / 14, adjust=False).mean()
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    out["bb_pctb"] = (c - (mid - 2 * sd)) / (4 * sd).replace(0, np.nan)
    out["rvol"] = v / v.shift(1).rolling(RVOL_DAYS).mean().replace(0, np.nan)
    obv = (np.sign(d).fillna(0) * v.fillna(0)).cumsum()
    out["obv_slope_pct"] = (obv - obv.shift(20)) / (v.rolling(20).mean() * 20).replace(0, np.nan) * 100
    tp = (h + l + c) / 3
    flow = tp * v
    pos = flow.where(tp > tp.shift(), 0.0).rolling(14).sum()
    neg = flow.where(tp < tp.shift(), 0.0).rolling(14).sum()
    out["mfi"] = 100 - 100 / (1 + pos / neg.replace(0, np.nan))
    out["mom_12_1"] = (c.shift(21) / c.shift(252) - 1) * 100   # momentum de 12 meses sin el último (Moskowitz et al., 2012)
    out["dist_52w_high"] = (c / h.rolling(252).max() - 1) * 100
    out["sma200"] = c.rolling(SMA_LONG).mean()
    return out


def _ultimo(serie: pd.Series) -> float | None:
    v = serie.iloc[-1] if len(serie) else np.nan
    return None if pd.isna(v) else round(float(v), 4)


def dividend_stats(divs: pd.Series | None, ref: pd.Timestamp) -> dict:
    """Dividendo de 12 meses, crecimiento y CAGR a 5 años (año calendario completo más reciente contra 5 años antes),
    años seguidos pagando y pagos en el último año completo."""
    out = {"dividend_12m": None, "dividend_growth_5y_pct": None, "dividend_cagr_5y_pct": None, "dividend_years": None, "dividend_payments_last_year": None}
    if divs is None or len(divs) == 0:
        return out
    last = divs[divs.index > ref - pd.DateOffset(years=1)]
    out["dividend_12m"] = round(float(last.sum()), 4) if len(last) else 0.0
    por_anio = divs.groupby(divs.index.year).sum()
    y = ref.year - 1
    if y in por_anio.index:
        out["dividend_payments_last_year"] = int((divs.index.year == y).sum())
        if (y - 5) in por_anio.index and por_anio[y - 5] > 0:
            a, b = float(por_anio[y - 5]), float(por_anio[y])
            out["dividend_growth_5y_pct"] = round((b / a - 1) * 100, 2)
            out["dividend_cagr_5y_pct"] = round(((b / a) ** (1 / 5) - 1) * 100, 2) if b > 0 else None
        n, k = 0, y
        while k in por_anio.index and por_anio[k] > 0:
            n += 1; k -= 1
        out["dividend_years"] = n
    return out


def trailing_dividend_yield(divs: pd.Series | None, price: float | None, ref=None) -> float | None:
    """Rendimiento por dividendo de 12 meses calculado aquí: dividendos pagados en el último año / precio actual."""
    if divs is None or len(divs) == 0 or not price:
        return None
    ref = ref if ref is not None else divs.index[-1]
    last = divs[divs.index > ref - pd.DateOffset(years=1)]
    return round(float(last.sum()) / price * 100, 2) if len(last) else None


def _double(levels: np.ndarray, opposite: np.ndarray, closes: np.ndarray, pivots: list[int],
            atr_value: float | None, bottom: bool, tol: float, min_gap: int, max_age: int) -> bool:
    """Doble piso (bottom=True) o doble techo confirmado.

    Dos pivotes a menos de `tol` % entre sí, separados al menos `min_gap` días, con un rebote (o caída) entre ellos
    de al menos DOUBLE_MIN_SWING_ATR × ATR, el segundo dentro de los últimos `max_age` días, y el cierre actual ya
    rompió la «línea de cuello» (el extremo opuesto entre los dos toques). Criterios de Bulkowski adaptados al ATR.
    """
    if not atr_value or len(pivots) < 2:
        return False
    n = len(closes)
    for j in range(len(pivots) - 1, 0, -1):
        b = pivots[j]
        if n - 1 - b > max_age:
            break
        for i in range(j - 1, -1, -1):
            a = pivots[i]
            if b - a < min_gap:
                continue
            la, lb = levels[a], levels[b]
            if la <= 0 or abs(lb - la) / la * 100 > tol:
                continue
            between = opposite[a:b + 1]
            neck = between.max() if bottom else between.min()
            swing = (neck - max(la, lb)) if bottom else (min(la, lb) - neck)
            if swing < DOUBLE_MIN_SWING_ATR * atr_value:
                continue
            if (closes[-1] > neck) if bottom else (closes[-1] < neck):
                return True
    return False


def detect_double_touch(daily: pd.DataFrame, lookback: int = DOUBLE_LOOKBACK,
                        tol: float = DOUBLE_TOUCH_TOL, atr_value: float | None = None,
                        min_gap: int = DOUBLE_MIN_GAP, max_age: int = DOUBLE_MAX_AGE) -> tuple[bool, bool]:
    recent = daily.tail(lookback)
    atr_value = atr_value if atr_value is not None else atr(daily)
    highs, lows, closes = recent["High"].values, recent["Low"].values, recent["Close"].values
    high_pivots, _ = find_pivots(highs)
    _, low_pivots = find_pivots(lows)
    # Una meseta (mismo extremo varios días) cuenta como un solo pivote.
    high_pivots = [i for k, i in enumerate(high_pivots) if k == 0 or i - high_pivots[k - 1] > 1]
    low_pivots = [i for k, i in enumerate(low_pivots) if k == 0 or i - low_pivots[k - 1] > 1]
    return (_double(lows, highs, closes, low_pivots, atr_value, True, tol, min_gap, max_age),
            _double(highs, lows, closes, high_pivots, atr_value, False, tol, min_gap, max_age))


# --------------------------------------------------------------------------- #
# Acceso a datos con reintentos.
# --------------------------------------------------------------------------- #
def _history(tk: yf.Ticker, **kwargs) -> pd.DataFrame:
    """history() con reintentos y espera progresiva si Yahoo falla o limita."""
    last = pd.DataFrame()
    for attempt in range(MAX_RETRIES):
        try:
            df = tk.history(**kwargs)
            if not df.empty:
                return df
            last = df
        except Exception:
            pass
        time.sleep(1.5 * (attempt + 1))
    return last


def _currency(tk: yf.Ticker) -> str | None:
    try:
        c = tk.fast_info.get("currency")
        if c:
            return c
    except Exception:
        pass
    return _safe_info(tk, "currency")


# Precios diarios ya descargados (los usa backtest.py en la misma corrida).
_DAILY: dict[str, pd.DataFrame] = {}

# Tipos de cambio a USD (se llenan una vez en main para normalizar la liquidez).
_FX = {"USD": 1.0}


def get_fx_rates() -> dict:
    """Devuelve cuántos USD vale 1 unidad de cada divisa (USD=1)."""
    rates = {"USD": 1.0}
    try:
        m = yf.Ticker("MXN=X").history(period="5d")["Close"].dropna()
        if len(m):
            rates["MXN"] = 1.0 / float(m.iloc[-1])   # MXN=X es MXN por USD
    except Exception:
        pass
    try:
        e = yf.Ticker("EURUSD=X").history(period="5d")["Close"].dropna()
        if len(e):
            rates["EUR"] = float(e.iloc[-1])         # USD por EUR
    except Exception:
        pass
    for cur in ("CAD", "GBP", "CHF", "JPY"):
        try:
            x = yf.Ticker(f"{cur}USD=X").history(period="5d")["Close"].dropna()
            if len(x):
                rates[cur] = float(x.iloc[-1])           # USD por unidad
        except Exception:
            pass
    return rates


def classify_liquidity(value_usd: float | None) -> str:
    """Clasifica según el valor promedio operado por día (en USD)."""
    if value_usd is None or value_usd != value_usd or value_usd <= 0:
        return "sin dato"
    if value_usd >= LIQ_HIGH_USD:
        return "alta"
    if value_usd >= LIQ_MED_USD:
        return "media"
    return "baja"


def analyze_ticker(ticker: str) -> Analysis:
    res = Analysis(ticker=ticker)
    res.name, res.sector = META.get(ticker, (None, None))
    res.dividend_group = DIV_GROUP.get(ticker)
    try:
        tk = yf.Ticker(ticker)
        # Precios ajustados por splits y dividendos: sin esto, un split (p. ej. 10 a 1) deja máximos históricos falsos.
        daily = _history(tk, period="10y", interval="1d", auto_adjust=True)
        if daily.empty:
            res.ok = False
            res.error = "Sin datos (ticker inválido o Yahoo lo limitó)"
            return res
        daily = daily.dropna(subset=["High", "Low", "Close"])
        _DAILY[ticker] = daily

        current = float(daily["Close"].iloc[-1])
        res.current_price = current
        res.high_10y, res.low_10y = price_extremes(daily, 10)
        res.high_5y, res.low_5y = price_extremes(daily, 5)
        res.high_1y, res.low_1y = price_extremes(daily, 1)

        cutoff = daily.index[-1] - pd.DateOffset(years=1)
        res.sparkline_12m = [round(v, 4) for v in
                             daily[daily.index >= cutoff]["Close"].tolist()]

        weekly_close = daily["Close"].resample("W-FRI").last().dropna()
        res.trend, res.trend_pct_per_week = weekly_trend(weekly_close)

        ind = indicator_series(daily)
        res.rsi_14 = _ultimo(ind["rsi"]); res.macd_hist = _ultimo(ind["macd_hist"]); res.adx_14 = _ultimo(ind["adx"])
        res.bb_pctb = _ultimo(ind["bb_pctb"]); res.rvol = _ultimo(ind["rvol"]); res.obv_slope_pct = _ultimo(ind["obv_slope_pct"])
        res.mfi_14 = _ultimo(ind["mfi"]); res.mom_12_1_pct = _ultimo(ind["mom_12_1"]); res.dist_52w_high_pct = _ultimo(ind["dist_52w_high"])
        res.atr_14 = atr(daily)
        res.sma_200 = sma(daily["Close"])
        res.above_sma200 = (current > res.sma_200) if res.sma_200 else None
        res.support, res.resistance = support_resistance(daily, current)
        res.dist_to_support_pct = round((current - res.support) / current * 100, 2) if res.support else None
        res.dist_to_resistance_pct = round((res.resistance - current) / current * 100, 2) if res.resistance else None
        res.double_bottom, res.double_top = detect_double_touch(daily, atr_value=res.atr_14)

        _fill_dividends(tk, res)
        if not res.name:
            res.name = _safe_info(tk, "shortName") or _safe_info(tk, "longName")
        if not res.sector:
            sec = _safe_info(tk, "sector")
            res.sector = DIV.SECTOR_ES.get(sec, sec) if sec else ("Dividendos S&P 500" if res.dividend_group == "sp500" else None)
        _fill_news(tk, res)
        res.currency = _currency(tk)
        # Precio actual convertido a MXN (para el filtro de precio).
        try:
            usd_rate = _FX.get(res.currency or "USD")
            mxn_rate = _FX.get("MXN")
            if res.current_price is not None and mxn_rate and usd_rate:
                res.price_mxn = round(res.current_price * usd_rate / mxn_rate, 2)
        except Exception:
            pass

        # Liquidez: valor promedio operado por día (30d), normalizado a USD.
        try:
            res.avg_volume_30d = float(daily["Volume"].tail(30).mean())
            val_local = float((daily["Close"] * daily["Volume"]).tail(30).mean())
            rate = _FX.get(res.currency or "USD")
            res.avg_value_30d_usd = round(val_local * rate, 2) if rate else None
            res.liquidity = classify_liquidity(res.avg_value_30d_usd)
        except Exception:
            res.liquidity = "sin dato"
        return res
    except Exception as exc:  # noqa: BLE001
        res.ok = False
        res.error = f"{type(exc).__name__}: {exc}"
        return res


def _fill_dividends(tk: yf.Ticker, res: Analysis) -> None:
    try:
        divs = tk.dividends
        if divs is not None and len(divs) > 0:
            res.pays_dividend = True
            res.last_dividend = float(divs.iloc[-1])
            res.last_dividend_date = divs.index[-1].date().isoformat()
    except Exception:
        pass
    # Rendimiento de 12 meses calculado con los dividendos pagados y el precio actual. Antes se tomaba
    # «dividendYield» de Yahoo, que ya viene en % y se multiplicaba otra vez por 100 (MSFT salía con 74 %).
    try:
        ref = pd.Timestamp.now(tz=tk.dividends.index.tz)
        res.dividend_yield_pct = trailing_dividend_yield(tk.dividends, res.current_price, ref)
        for k, v in dividend_stats(tk.dividends, ref).items():
            setattr(res, k, v)
    except Exception:
        res.dividend_yield_pct = None
    ex = _safe_info(tk, "exDividendDate")
    if ex:
        try:
            res.next_ex_dividend_date = datetime.fromtimestamp(
                ex, tz=timezone.utc).date().isoformat()
        except (TypeError, ValueError, OSError):
            res.next_ex_dividend_date = str(ex)


_PRICE_NOISE_RE = re.compile(
    r"why\s+[\w\s.,'-]{0,60}(stock|shares?)\s+[\w\s.,'-]{0,40}(is|was|are|were)\s+(up|down)"
    r"|(stock|shares?)\s+[\w\s.,'-]{0,40}(up|down|rose|fell|gained|lost|jumped|dropped|surged|plunged|climbed|slid)\s+[\w\s.,'-]{0,40}today"
    r"|today'?s?\s+(stock\s+)?price"
    r"|(stock|share)\s+price\s+(today|now)"
    r"|here'?s\s+why"
    r"|\d+(\.\d+)?%\s+(higher|lower)\b"
    r"|pre[- ]?market|after[- ]?hours|closing bell|opening bell|market wrap|stocks?\s+to\s+watch",
    re.IGNORECASE,
)

def _is_price_noise(title: str) -> bool:
    return bool(_PRICE_NOISE_RE.search(title))

def _fill_news(tk: yf.Ticker, res: Analysis, limit: int = 5) -> None:
    try:
        items = list(tk.news or [])
    except Exception:
        items = []
    out = []
    for it in items:
        if len(out) >= limit:
            break
        c = it.get("content", it) if isinstance(it, dict) else {}
        title = c.get("title") if isinstance(c, dict) else None
        if not title or _is_price_noise(title):
            continue
        out.append({"title": title, "link": _news_link(c), "publisher": _news_publisher(c), "date": _news_date(c)})
    res.news = out
def _news_link(c: dict) -> str | None: ct = c.get("clickThroughUrl"); cu = c.get("canonicalUrl"); return (ct.get("url") if isinstance(ct, dict) and ct.get("url") else None) or (cu.get("url") if isinstance(cu, dict) and cu.get("url") else None) or c.get("link")

def _news_publisher(c: dict) -> str | None:
    prov = c.get("provider")
    if isinstance(prov, dict) and prov.get("displayName"):
        return prov["displayName"]
    return c.get("publisher")

def _news_date(c: dict) -> str | None:
    pub = c.get("pubDate") or c.get("providerPublishTime")
    if isinstance(pub, str):
        return pub
    if isinstance(pub, (int, float)):
        try:
            return datetime.fromtimestamp(pub, tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            return None
    return None
def _safe_info(tk: yf.Ticker, key: str):
    try:
        return tk.info.get(key)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Reporte.
# --------------------------------------------------------------------------- #
def near_levels(a: Analysis) -> tuple[bool, bool]:
    """Cerca = a menos de NEAR_ATR veces el ATR(14). Sin ATR, se usa 3 % como antes."""
    cur = a.current_price
    if not cur:
        return False, False
    lim = NEAR_ATR * a.atr_14 if a.atr_14 else cur * 0.03
    ns = a.support is not None and (cur - a.support) <= lim
    nr = a.resistance is not None and (a.resistance - cur) <= lim
    if ns and nr:   # rango tan estrecho que el precio está cerca de los dos: no cuenta ninguno
        return False, False
    return ns, nr


def classify(a: Analysis) -> dict:
    reasons: list[str] = []
    near_support, near_resistance = near_levels(a)
    score = 0
    if a.trend == "alcista":
        score += 1; reasons.append("Tendencia semanal alcista")
    elif a.trend == "bajista":
        score -= 1; reasons.append("Tendencia semanal bajista")
    if near_support:
        score += 1; reasons.append(f"Precio a menos de 1 ATR del soporte ({a.dist_to_support_pct}%)")
    if near_resistance:
        score -= 1; reasons.append(f"Precio a menos de 1 ATR de la resistencia ({a.dist_to_resistance_pct}%)")
    if a.double_bottom:
        score += 1; reasons.append("Doble piso confirmado (rompió la línea de cuello)")
    if a.double_top:
        score -= 1; reasons.append("Doble techo confirmado (rompió la línea de cuello)")
    if a.above_sma200 is True:
        reasons.append("Precio arriba de su media de 200 días")
    elif a.above_sma200 is False:
        reasons.append("Precio abajo de su media de 200 días")
    if a.liquidity == "baja":
        reasons.append("Liquidez baja — puede ser difícil comprar/vender")
    # Confirmaciones (indicadores internos). Una señal solo se emite si no la contradicen.
    bloqueos_compra, bloqueos_venta = [], []
    if a.above_sma200 is False:
        bloqueos_compra.append("precio abajo de su media de 200 días")
    if a.rsi_14 is not None and a.rsi_14 >= 70:
        bloqueos_compra.append(f"RSI en sobrecompra ({a.rsi_14:.0f})")
    if a.rsi_14 is not None and a.rsi_14 <= 30:
        bloqueos_venta.append(f"RSI en sobreventa ({a.rsi_14:.0f})")
    if a.mom_12_1_pct is not None and a.mom_12_1_pct < 0:
        bloqueos_compra.append(f"momentum de 12 meses negativo ({a.mom_12_1_pct:.1f} %)")
    if a.mom_12_1_pct is not None and a.mom_12_1_pct > 0 and a.above_sma200:
        bloqueos_venta.append("momentum de 12 meses positivo y arriba de su media de 200 días")
    if a.rvol is not None and a.rvol < RVOL_MIN:
        bloqueos_compra.append(f"volumen relativo bajo ({a.rvol:.2f}×)")
        bloqueos_venta.append(f"volumen relativo bajo ({a.rvol:.2f}×)")
    elif a.rvol is not None:
        reasons.append(f"Volumen relativo {a.rvol:.2f}× su promedio de 20 días")
    if score >= 2 and not bloqueos_compra:
        category = "comprar"
    elif score <= -2 and not bloqueos_venta:
        category = "vender"
    else:
        category = "esperar"
        if score >= 2:
            reasons.append("No confirma «comprar»: " + "; ".join(bloqueos_compra))
        if score <= -2:
            reasons.append("No confirma «vender»: " + "; ".join(bloqueos_venta))
    return {"category": category, "score": score, "reasons": reasons}


def build_report(results: list[Analysis]) -> dict:
    buckets = {"comprar": [], "vender": [], "esperar": [], "error": []}
    for a in results:
        if not a.ok:
            buckets["error"].append({"ticker": a.ticker, "name": a.name,
                                      "sector": a.sector, "error": a.error})
            continue
        c = classify(a)
        buckets[c["category"]].append({
            "ticker": a.ticker, "name": a.name, "sector": a.sector,
            "price": a.current_price, "trend": a.trend,
            "support": a.support, "resistance": a.resistance,
            "score": c["score"], "reasons": c["reasons"],
        })
    for k in ("comprar", "vender", "esperar"):
        buckets[k].sort(key=lambda x: x["score"], reverse=(k != "vender"))
    return {"generated_at": datetime.now(MX_TZ).isoformat(), "report": buckets}

def main() -> None:
    global _FX
    _FX = get_fx_rates()
    print(f"FX a USD: {_FX}", flush=True)
    results = []
    total = len(ALL_TICKERS)
    for i, t in enumerate(ALL_TICKERS, 1):
        print(f"[{i}/{total}] {t}", flush=True)
        results.append(analyze_ticker(t))
        time.sleep(SLEEP_BETWEEN)

    with open("portfolio_data.json", "w", encoding="utf-8") as fh:
        json.dump([asdict(a) for a in results], fh, ensure_ascii=False, indent=2)
    report = build_report(results)
    with open("daily_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    try:
        import backtest
        def clase(t):
            if t.endswith("-USD"):
                return "cripto"
            return "etf" if (META.get(t, (None, ""))[1] or "").lower().startswith(("etf", "fibra")) else "accion"
        bt = backtest.run(_DAILY, clase)
        with open("backtest.json", "w", encoding="utf-8") as fh:
            json.dump(bt, fh, ensure_ascii=False, indent=1)
        print(f"Backtest: {bt['tickers']} instrumentos", flush=True)
        for tramo, d in (("10 años", bt), ("últimos 3 años", bt["prueba"])):
            b = d["comprar_y_mantener"]
            print(f"  [{tramo}] comprar y mantener: acierto {b['acierto_pct']}% mediana {b['retorno_mediano_pct']}%", flush=True)
            for k, r in d["reglas"].items():
                print(f"  [{tramo}] {r['nombre']:<62} n={r['senales']:<6} acierto={r['acierto_pct']}% mediana={r['retorno_mediano_pct']}% media={r['retorno_medio_pct']}%", flush=True)
    except Exception as exc:  # noqa: BLE001  el reporte diario no depende del backtest
        print(f"Backtest no disponible: {type(exc).__name__}: {exc}", flush=True)

    ok = sum(1 for a in results if a.ok)
    print(f"\nReporte {report['generated_at']} — {ok}/{total} con datos\n")
    for cat in ("comprar", "vender", "esperar"):
        print(f"== {cat.upper()} ({len(report['report'][cat])}) ==")
        for item in report["report"][cat]:
            print(f"  {item['ticker']:<16} {item['price']:<12} score={item['score']:+d}")
    if report["report"]["error"]:
        print(f"\n== ERRORES ({len(report['report']['error'])}) ==")
        for e in report["report"]["error"]:
            print(f"  {e['ticker']}: {e['error']}")


if __name__ == "__main__":
    main()
