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
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

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
    "GFNORTEO.MX",    # Grupo Financiero Banorte — MXN
    "BBAJIOO.MX",     # Banco del Bajío — MXN
    "GENTERA.MX",     # Gentera (microfinanzas) — MXN

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
    "GFNORTEO.MX": ("Banorte", "Finanzas / Bancos"),
    "BBAJIOO.MX": ("Banco del Bajío", "Finanzas / Bancos"),
    "GENTERA.MX": ("Gentera", "Finanzas / Bancos"),
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

# Umbrales (ajústalos a tu gusto).
TREND_PCT_PER_WEEK = 0.5   # % por semana para considerar tendencia, no lateral
NEAR_LEVEL_PCT = 3.0       # qué tan cerca (%) de soporte/resistencia cuenta
PIVOT_ORDER = 3            # velas a cada lado para confirmar un pivote
DOUBLE_TOUCH_TOL = 1.5     # tolerancia (%) para considerar dos toques "iguales"
SLEEP_BETWEEN = 0.5        # pausa (seg) entre tickers para no saturar a Yahoo
MAX_RETRIES = 3            # reintentos por ticker si Yahoo falla/limita
LIQ_HIGH_USD = 10_000_000  # valor operado/día (USD) para liquidez "alta"
LIQ_MED_USD = 1_000_000    # umbral para liquidez "media" (abajo = "baja")


# --------------------------------------------------------------------------- #
@dataclass
class Analysis:
    ticker: str
    ok: bool = True
    error: str | None = None
    current_price: float | None = None
    currency: str | None = None
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
    double_bottom: bool = False
    double_top: bool = False
    pays_dividend: bool = False
    last_dividend: float | None = None
    last_dividend_date: str | None = None
    dividend_yield_pct: float | None = None
    next_ex_dividend_date: str | None = None
    avg_volume_30d: float | None = None
    avg_value_30d_usd: float | None = None   # valor operado/día normalizado a USD
    liquidity: str | None = None             # "alta" | "media" | "baja" | "sin dato"
    sparkline_12m: list[float] = field(default_factory=list)


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
    recent = daily.tail(lookback)
    high_pivots, _ = find_pivots(recent["High"].values)
    _, low_pivots = find_pivots(recent["Low"].values)
    res_levels = [recent["High"].values[i] for i in high_pivots
                  if recent["High"].values[i] > current]
    sup_levels = [recent["Low"].values[i] for i in low_pivots
                  if recent["Low"].values[i] < current]
    resistance = float(min(res_levels)) if res_levels else float(recent["High"].max())
    support = float(max(sup_levels)) if sup_levels else float(recent["Low"].min())
    return support, resistance


def detect_double_touch(daily: pd.DataFrame, lookback: int = 60,
                        tol: float = DOUBLE_TOUCH_TOL) -> tuple[bool, bool]:
    recent = daily.tail(lookback)
    high_pivots, _ = find_pivots(recent["High"].values)
    _, low_pivots = find_pivots(recent["Low"].values)

    def has_pair(idxs: list[int], series: np.ndarray) -> bool:
        levels = sorted(series[i] for i in idxs)
        for a, b in zip(levels, levels[1:]):
            if a > 0 and abs(b - a) / a * 100 <= tol:
                return True
        return False

    return (has_pair(low_pivots, recent["Low"].values),
            has_pair(high_pivots, recent["High"].values))


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
    try:
        tk = yf.Ticker(ticker)
        daily = _history(tk, period="10y", interval="1d", auto_adjust=False)
        if daily.empty:
            res.ok = False
            res.error = "Sin datos (ticker inválido o Yahoo lo limitó)"
            return res
        daily = daily.dropna(subset=["High", "Low", "Close"])

        current = float(daily["Close"].iloc[-1])
        res.current_price = current
        res.high_10y, res.low_10y = price_extremes(daily, 10)
        res.high_5y, res.low_5y = price_extremes(daily, 5)
        res.high_1y, res.low_1y = price_extremes(daily, 1)

        cutoff = daily.index[-1] - pd.DateOffset(years=1)
        res.sparkline_12m = [round(v, 4) for v in
                             daily[daily.index >= cutoff]["Close"].tolist()]

        weekly = _history(tk, period="6mo", interval="1wk", auto_adjust=False)
        if not weekly.empty:
            res.trend, res.trend_pct_per_week = weekly_trend(weekly["Close"])

        res.support, res.resistance = support_resistance(daily, current)
        res.dist_to_support_pct = round((current - res.support) / current * 100, 2)
        res.dist_to_resistance_pct = round((res.resistance - current) / current * 100, 2)
        res.double_bottom, res.double_top = detect_double_touch(daily)

        _fill_dividends(tk, res)
        res.currency = _currency(tk)

        # Liquidez: valor promedio operado por día (30d), normalizado a USD.
        try:
            res.avg_volume_30d = float(daily["Volume"].tail(30).mean())
            val_local = float((daily["Close"] * daily["Volume"]).tail(30).mean())
            rate = _FX.get(res.currency or "USD", 1.0)
            res.avg_value_30d_usd = round(val_local * rate, 2)
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
    y = _safe_info(tk, "dividendYield")
    if y is not None:
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
# Reporte.
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
    if a.liquidity == "baja":
        reasons.append("Liquidez baja — puede ser difícil comprar/vender")
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
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "report": buckets}


def main() -> None:
    global _FX
    _FX = get_fx_rates()
    print(f"FX a USD: {_FX}", flush=True)
    results = []
    total = len(WATCHLIST)
    for i, t in enumerate(WATCHLIST, 1):
        print(f"[{i}/{total}] {t}", flush=True)
        results.append(analyze_ticker(t))
        time.sleep(SLEEP_BETWEEN)

    with open("portfolio_data.json", "w", encoding="utf-8") as fh:
        json.dump([asdict(a) for a in results], fh, ensure_ascii=False, indent=2)
    report = build_report(results)
    with open("daily_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

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
