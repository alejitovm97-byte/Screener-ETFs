"""Configuración compartida: fondos, pesos objetivo y parámetros de la metodología."""
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
RESULTS = Path(__file__).resolve().parent.parent / "resultados"
DATA.mkdir(exist_ok=True)
RESULTS.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Paso 2: filtros duros y casilleros del screener
# ---------------------------------------------------------------------------
MIN_SIZE_M_EUR = 100          # tamaño mínimo para entrar al ranking de eficiencia
TIE_PP_PER_YEAR = 0.3         # diferencias menores se consideran empate
RANK_WEIGHTS = {"seguimiento": 0.40, "costo": 0.20, "tamano": 0.20, "historia": 0.20}

# Palabras que excluyen variantes que no replican el índice puro
EXCLUDE = (r"emu|esg|sri|climate|paris|screened|responsible|equal|top 30|ex-top|covered|buffer|"
           r"premium|income|next gen|imi|ex china|ex-china|asia|small|value|minimum vol|min vol|"
           r"consumer|latin|dividend|factor|enhanced|transition|biotech|tech|innovation|leaders")

# Casilleros de índice puro: se rankean por eficiencia (mismo índice, distinta implementación)
INDEX_SLOTS = {
    "Nasdaq 100": r"nasdaq[- ]?100",
    "MSCI World ex USA": r"msci world ex[- ]usa",
    "MSCI Emerging Markets": r"msci (?:em\b|emerging)",
}

# ---------------------------------------------------------------------------
# Paso 3: lista corta para bajar historia de precios
# key: (ISIN, casillero, grupo). grupo: indice | estrategia | ref
# ---------------------------------------------------------------------------
SHORTLIST = {
    "ndx_bnp":      ("IE000QDFFK00", "Nasdaq 100", "indice"),
    "ndx_invesco":  ("IE00BNRQM384", "Nasdaq 100", "indice"),
    "ndx_xtrackers":("IE00BMFKG444", "Nasdaq 100", "indice"),
    "ndx_ishares":  ("IE00B53SZB19", "Nasdaq 100", "indice"),
    "exus_xtr":     ("IE0006WW1TQ4", "Ex-EEUU", "indice"),
    "exus_ishares": ("IE000R4ZNTN3", "Ex-EEUU", "indice"),
    "em_ishares":   ("IE00B4L5YC18", "Emergentes", "indice"),
    "em_spdr":      ("IE00B469F816", "Emergentes", "indice"),
    "em_imi":       ("IE00BKM4GZ66", "Emergentes", "estrategia"),
    "em_avantis":   ("IE000K975W13", "Emergentes", "estrategia"),
    "em_value":     ("IE00BG0SKF03", "Emergentes", "estrategia"),
    "scv_avantis":  ("IE0003R87OG3", "Small caps", "estrategia"),
    "scv_spdr_us":  ("IE00BSPLC413", "Small caps", "estrategia"),
    "scv_spdr_eu":  ("IE00BSPLC298", "Small caps", "estrategia"),
    "sc_world":     ("IE00BF4RFH31", "Small caps", "ref"),
    "sc_russell":   ("IE00BJ38QD84", "Small caps", "ref"),
    "cmd_rollsel":  ("IE00BZ1NCS44", "Commodities", "estrategia"),
    "gold":         ("IE00B4ND3602", "Oro", "indice"),
}

# ETFs estadounidenses con historia larga (proxies para los fondos nuevos)
PROXIES = {
    "qqq": "QQQ", "efa": "EFA", "eem": "EEM", "avem": "AVEM", "avuv": "AVUV", "avdv": "AVDV",
    "grid": "GRID", "nlr": "NLR", "ita": "ITA", "qtum": "QTUM", "acwi": "ACWI", "bil": "BIL",
}

# ---------------------------------------------------------------------------
# Paso 5: cartera objetivo y la serie usada para simular cada casillero
# ---------------------------------------------------------------------------
TARGET = {"ndx": 0.30, "exus": 0.15, "scv": 0.15, "emv": 0.10, "cmd": 0.05, "gold": 0.05,
          "grid": 0.08, "nucl": 0.07, "dfns": 0.03, "qntm": 0.02}
CORE = {"ndx", "exus", "scv", "emv"}
SIM_SERIES = {"ndx": "ndx_ishares", "exus": "efa", "emv": "em_value", "cmd": "cmd_rollsel",
              "gold": "gold", "grid": "grid", "nucl": "nlr", "dfns": "ita", "qntm": "qtum"}
SCV_MIX = {"avuv": 0.68, "avdv": 0.32}   # pesos por país del Avantis global (68% EE.UU.)

MONTHLY = 1000.0
FEE = 2.0
RULE = {"max_buys": 3, "min_ticket": 250.0, "vol_step": 1.0, "cap": 3.0}
