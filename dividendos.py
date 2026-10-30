"""Listas de acciones con dividendo que sigue el Portafolio (además de WATCHLIST).

DIV_SP500: lista del S&P 500 con dividendo que compartió la persona dueña del proyecto (sin las que ya no cotizan).
DIV_MX: emisoras de la Bolsa Mexicana que pagan dividendo, incluidas Coca-Cola (KOF, Arca Continental),
y las relacionadas con Carlos Slim (América Móvil, Carso, Inbursa, Frisco, Sanborns, Telesites, IDEAL).
Los montos de dividendo NO se copian de ninguna lista: se calculan cada día con los dividendos realmente pagados.
"""

RETIRADAS = {'MRO': 'comprada por ConocoPhillips (2024)', 'HES': 'comprada por Chevron (2025)', 'JNPR': 'comprada por HPE (2025)', 'DFS': 'comprada por Capital One (2025)', 'WBA': 'salió de bolsa (2025)', 'PARA': 'ahora es PSKY (Paramount Skydance)'}

DIV_SP500 = [
    "DOW", "LYB", "CAG", "MO", "ARE", "PFE", "DOC", "UPS", "VZ", "F", "EIX", "KHC",
    "CCI", "AES", "FMC", "O", "HST", "BBY", "IPG", "VTRS", "AMCR", "VICI", "SPG", "APA",
    "BEN", "BMY", "PRU", "OKE", "CPB", "TROW", "TDG", "IVZ", "GIS", "D", "FRT", "HPQ",
    "KIM", "TFC", "SWK", "ES", "KEY", "CVX", "EXR", "TGT", "FE", "USB", "UDR", "EMN",
    "PSA", "SJM", "BXP", "CVS", "KMI", "EQR", "RF", "PEP", "REG", "MAA", "KMB", "PNW",
    "EVRG", "HRL", "OMC", "CLX", "CME", "MRK", "KVUE", "SWKS", "ADM", "HAS", "FANG", "TAP",
    "PFG", "TSN", "BG", "HBAN", "CPT", "PLD", "ETR", "EXC", "PSX", "DUK", "CMCSA", "IP",
    "INVH", "CFG", "AEP", "ESS", "XOM", "DVN", "SRE", "AVB", "WEC", "CTRA", "FITB", "ABBV",
    "SYY", "ED", "HSY", "WMB", "COP", "GPC", "PNC", "XEL", "FAST", "WY", "AMGN", "JNJ",
    "DTE", "LNT", "BF-B", "SW", "SO", "LKQ", "MDT", "EOG", "PPL", "SLB", "HAL", "IRM",
    "T", "AMT", "CMS", "PEG", "VLO", "NEE", "DLR", "AEE", "KO", "K", "LW", "VTR",
    "UNH", "MET", "BAX", "PAYX", "MDLZ", "GILD", "STT", "LMT", "NI", "KDP", "SNA", "MTB",
    "DRI", "PG", "C", "MS", "SBUX", "CHRW", "BBWI", "MKC", "HPE", "BX", "HD", "MCHP",
    "STZ", "CE", "TXN", "APD", "CNP", "PKG", "MOS", "FDX", "NTRS", "CSCO", "IBM", "EQIX",
    "PPG", "EG", "TRGP", "ITW", "BDX", "MCD", "UNP", "WRB", "CL", "ALB", "AFL", "CINF",
    "PM", "QCOM", "BAC", "BKR", "ATO", "AWK", "NKE", "CMI", "IFF", "GLW", "DD", "ACN",
    "DG", "MPC", "LOW", "HII", "CF", "NSC", "OXY", "ADP", "AIG", "PGR", "BK", "NTAP",
    "AVY", "ELV", "ALL", "AOS", "CI", "STX", "WFC", "FIS", "LUV", "EL", "GD", "HON",
    "BLK", "YUM", "JPM", "MAS", "MMM", "DGX", "NXPI", "SBAC", "LHX", "LVS", "KR", "LEN",
    "RTX", "ABT", "WELL", "HIG", "AIZ", "GS", "GEN", "TRV", "NEM", "NOC", "CTSH", "POOL",
    "OTIS", "ADI", "TSCO", "HUM", "TMUS", "IEX", "MMC", "ROK", "EMR", "TEL", "BR", "SYF",
    "CSX", "GRMN", "EBAY", "STLD", "CAT", "JCI", "TPR", "MKTX", "CDW", "BALL", "WM", "DPZ",
    "ALLE", "CB", "EXPD", "DAL", "JKHY", "ZTS", "TJX", "CAH", "HUBB", "DE", "GPN", "BWA",
    "LIN", "RJF", "ROL", "ROST", "CHD", "DHI", "MSCI", "RL", "TFX", "XYL", "WTW", "NUE",
    "LH", "JBHT", "NRG", "CARR", "SCHW", "AMP", "ETN", "NDAQ", "COF", "EQT", "DOV", "NDSN",
    "CBOE", "FOX", "MSI", "ICE", "ZBH", "STE", "PCAR", "FCX", "CTAS", "FOXA", "ECL", "LDOS",
    "GM", "AXP", "PH", "RSG", "CTVA", "FDS", "WMT", "LRCX", "WYNN", "PNR", "MAR", "RCL",
    "MPWR", "SHW", "J", "URI", "SYK", "GL", "AMAT", "AVGO", "RMD", "DIS", "KLAC", "A",
    "TT", "GWW", "AJG", "PHM", "CRM", "AON", "LLY", "ORCL", "COR", "HCA", "MCO", "VMC",
    "SPGI", "PAYC", "NWSA", "V", "APH", "AME", "ODFL", "MSFT", "BKNG", "EFX", "FTV", "ROP",
    "TECH", "DHR", "NWS", "MLM", "BRO", "INTU", "GE", "VRSK", "INTC", "PCG", "KKR", "EA",
    "TER", "COST", "AAPL", "CEG", "VST", "GOOGL", "GOOG", "UHS", "WAB", "VLTO", "MCK", "MA",
    "MU", "TMO", "WST", "RVTY", "META", "L", "HLT", "HWM", "GEHC", "JBL", "PWR", "TXT",
    "IR", "COO", "NVDA", "CBRE",
]

# (ticker de Yahoo, nombre, sector)
DIV_MX = [
    ('KOFUBL.MX', 'Coca-Cola FEMSA', 'Consumo básico'),
    ('AC.MX', 'Arca Continental (embotelladora de Coca-Cola)', 'Consumo básico'),
    ('FEMSAUBD.MX', 'FEMSA (OXXO)', 'Consumo básico'),
    ('WALMEX.MX', 'Walmart de México', 'Consumo básico'),
    ('BIMBOA.MX', 'Grupo Bimbo', 'Consumo básico'),
    ('GRUMAB.MX', 'Gruma (Maseca)', 'Consumo básico'),
    ('KIMBERA.MX', 'Kimberly-Clark de México', 'Consumo básico'),
    ('CHDRAUIB.MX', 'Chedraui', 'Consumo básico'),
    ('LACOMERUBC.MX', 'La Comer', 'Consumo básico'),
    ('CUERVO.MX', 'Becle (José Cuervo)', 'Consumo básico'),
    ('AMXB.MX', 'América Móvil (Carlos Slim)', 'Comunicaciones'),
    ('GCARSOA1.MX', 'Grupo Carso (Carlos Slim)', 'Conglomerado'),
    ('GFINBURO.MX', 'Grupo Financiero Inbursa (Carlos Slim)', 'Servicios financieros'),
    ('MFRISCOA-1.MX', 'Minera Frisco (Carlos Slim)', 'Minería / Metales'),
    ('GSANBORB-1.MX', 'Grupo Sanborns (Carlos Slim)', 'Consumo discrecional'),
    ('SITESB-1.MX', 'Telesites (Carlos Slim)', 'Comunicaciones'),
    ('IDEALB-1.MX', 'IDEAL, infraestructura (Carlos Slim)', 'Industria / Infraestructura'),
    ('GFNORTEO.MX', 'Grupo Financiero Banorte', 'Servicios financieros'),
    ('BOLSAA.MX', 'Bolsa Mexicana de Valores', 'Servicios financieros'),
    ('Q.MX', 'Quálitas (seguros)', 'Servicios financieros'),
    ('GENTERA.MX', 'Gentera', 'Servicios financieros'),
    ('BBAJIOO.MX', 'Banco del Bajío', 'Servicios financieros'),
    ('ASURB.MX', 'Grupo Aeroportuario del Sureste', 'Industria / Infraestructura'),
    ('GAPB.MX', 'Grupo Aeroportuario del Pacífico', 'Industria / Infraestructura'),
    ('OMAB.MX', 'Grupo Aeroportuario Centro Norte', 'Industria / Infraestructura'),
    ('PINFRA.MX', 'Pinfra (autopistas)', 'Industria / Infraestructura'),
    ('MEGACPO.MX', 'Megacable', 'Comunicaciones'),
    ('GCC.MX', 'GCC (cemento)', 'Materiales básicos'),
    ('CEMEXCPO.MX', 'Cemex', 'Materiales básicos'),
    ('GMEXICOB.MX', 'Grupo México', 'Minería / Metales'),
    ('ORBIA.MX', 'Orbia', 'Materiales básicos'),
]

# Empresas en EUA relacionadas con Carlos Slim (accionista relevante) que pagan dividendo.
DIV_SLIM_EUA = [("NYT", "The New York Times Company (Carlos Slim es accionista)", "Comunicaciones")]

SECTOR_ES = {"Basic Materials": "Materiales básicos", "Consumer Defensive": "Consumo básico", "Real Estate": "Bienes raíces (REIT)",
             "Healthcare": "Salud", "Industrials": "Industria", "Communication Services": "Comunicaciones", "Consumer Cyclical": "Consumo discrecional",
             "Utilities": "Servicios públicos (luz, gas, agua)", "Energy": "Energía", "Financial Services": "Servicios financieros", "Technology": "Tecnología"}
