"""Paso 1: descarga el universo completo de ETFs de justETF (una tabla, ~3 consultas).

Usa la librería no oficial justetf-scraping:
    pip install git+https://github.com/druzsan/justetf-scraping.git
"""
import justetf_scraping
from config import DATA

df = justetf_scraping.load_overview()
out = DATA / "universo_justetf.csv"
df.to_csv(out)
print(f"{len(df)} ETFs guardados en {out}")

"""Paso 2: filtros duros, casilleros y ranking de eficiencia.

Cada criterio se convierte en percentil dentro del casillero (0 = peor, 100 = mejor)
y se pondera. Rankear por posición y no por distancia evita que diferencias mínimas
parezcan enormes.
"""
import numpy as np
import pandas as pd
from config import DATA, RESULTS, EXCLUDE, INDEX_SLOTS, MIN_SIZE_M_EUR, RANK_WEIGHTS, TIE_PP_PER_YEAR

u = pd.read_csv(DATA / "universo_justetf.csv")
if "isin" not in u.columns:
    u = u.rename(columns={u.columns[0]: "isin"})
print(f"Universo: {len(u)} ETFs")

# 1. Filtros duros
u = u[(u.domicile_country == "Ireland") & (u.dividends == "Accumulating")
      & (~u.hedged.astype(bool)) & (u.strategy != "Short & Leveraged")]
print(f"Irlanda + acumulación + sin cobertura + sin apalancados: {len(u)}")


def percentile(s: pd.Series, higher_is_better=True) -> pd.Series:
    """Percentil de 0 a 100 dentro del grupo; los valores faltantes quedan en NaN."""
    r = s.rank(pct=False, ascending=higher_is_better, method="average")
    n = s.notna().sum()
    return (r - 1) / (n - 1) * 100 if n > 1 else r * 0 + 100


rankings = []
for slot, pattern in INDEX_SLOTS.items():
    g = u[u.name.str.contains(pattern, case=False)
          & ~u.name.str.contains(EXCLUDE, case=False)
          & (u["size"] >= MIN_SIZE_M_EUR)].copy()

    # Seguimiento: promedio de los percentiles de rendimiento a 1 y 3 años disponibles
    g["p_seguimiento"] = pd.concat([percentile(g.last_year), percentile(g.last_three_years)], axis=1).mean(axis=1)
    g["p_costo"] = percentile(g.ter, higher_is_better=False)
    g["p_tamano"] = percentile(g["size"])
    g["p_historia"] = percentile(g.age_in_years.clip(upper=10))
    parts = {k: g[f"p_{k}"].fillna(50) for k in RANK_WEIGHTS}
    g["puntaje"] = sum(parts[k] * w for k, w in RANK_WEIGHTS.items())
    g = g.sort_values("puntaje", ascending=False)

    # Empates: diferencia anualizada a 3 años contra el mejor menor al umbral
    best3 = g.last_three_years.max()
    ann = lambda x: ((1 + x / 100) ** (1 / 3) - 1) * 100
    gap = ann(best3) - ann(g.last_three_years)
    g["empate_con_el_mejor"] = (gap < TIE_PP_PER_YEAR).where(gap.notna())   # vacío si no hay 3 años
    g.insert(0, "casillero", slot)
    rankings.append(g)
    print(f"\n{slot}: {len(g)} fondos")
    print(g[["name", "ter", "size", "last_year", "last_three_years", "puntaje"]].round(1).head(8).to_string(index=False))

cols = ["casillero", "isin", "name", "ter", "size", "age_in_years", "last_year", "last_three_years",
        "last_five_years", "last_three_years_volatility", "max_drawdown", "p_seguimiento", "p_costo",
        "p_tamano", "p_historia", "puntaje", "empate_con_el_mejor"]
pd.concat(rankings)[cols].round(2).to_csv(RESULTS / "ranking_eficiencia.csv", index=False)
print(f"\nRanking guardado en {RESULTS / 'ranking_eficiencia.csv'}")

"""Paso 3: historia de precios de la lista corta (justETF) y de los proxies (Yahoo Finance).

Los fondos de acumulación reinvierten dividendos, así que su precio ya es rendimiento total.
Para los proxies estadounidenses se usa el precio ajustado por dividendos.
"""
import time
import pandas as pd
import justetf_scraping
import yfinance as yf
from config import DATA, SHORTLIST, PROXIES

series = {}
for key, (isin, *_ ) in SHORTLIST.items():
    try:
        try:
            df = justetf_scraping.load_chart(isin, currency="USD")
        except TypeError:
            df = justetf_scraping.load_chart(isin)
        col = "quote_with_dividends" if "quote_with_dividends" in df.columns else "quote"
        s = df[col].astype(float)
        s.index = pd.to_datetime(s.index)
        series[key] = s.sort_index()
        print(f"OK {key} desde {s.index[0].date()}")
    except Exception as e:
        print(f"ERROR {key}: {e!r}")
    time.sleep(1.5)   # no saturar el sitio

for key, ticker in PROXIES.items():
    h = yf.Ticker(ticker).history(period="max", auto_adjust=True)["Close"]
    h.index = h.index.tz_localize(None).normalize()
    series[key] = h
    print(f"OK {key} ({ticker}) desde {h.index[0].date()}")

precios = pd.DataFrame(series).sort_index()
precios.to_csv(DATA / "precios.csv")
print(f"Guardado {DATA / 'precios.csv'}: {precios.shape}")


"""Paso 4: rendimientos anualizados de 1 a 10 años, volatilidad, caída máxima y Sharpe."""
import numpy as np
import pandas as pd
from config import DATA, RESULTS

p = pd.read_csv(DATA / "precios.csv", index_col=0, parse_dates=True)
end = p.index[-1]
monthly = p.resample("ME").last()
rf = monthly["bil"].pct_change()

rows = []
for c in p.columns:
    s = p[c].dropna()
    out = {"serie": c, "desde": s.index[0].date()}
    for n in [1, 2, 3, 4, 5, 7, 10]:
        t = end - pd.DateOffset(years=n)
        if s.index[0] <= t + pd.Timedelta(days=10):
            v0 = s[:t].iloc[-1] if len(s[:t]) else s.iloc[0]
            out[f"{n}a_%"] = ((s.iloc[-1] / v0) ** (1 / n) - 1) * 100
    mr = monthly[c].dropna().pct_change().dropna()
    last5 = mr[mr.index > end - pd.DateOffset(years=5)]
    if len(last5) > 24:
        out["vol_5a_%"] = last5.std() * np.sqrt(12) * 100
        ex = (last5 - rf.reindex(last5.index)).dropna()
        out["sharpe_5a"] = ex.mean() / ex.std() * np.sqrt(12)
    out["caida_max_%"] = (s / s.cummax() - 1).min() * 100
    rows.append(out)

m = pd.DataFrame(rows).set_index("serie").round(2)
m.to_csv(RESULTS / "metricas.csv")
print(m.to_string())

years = (p.resample("YE").last().pct_change() * 100).round(1)
years.index = years.index.year
years.T.to_csv(RESULTS / "rendimientos_anuales.csv")

"""Paso 5: simulación de la regla de compra mensual contra alternativas.

Regla: prioridad = déficit frente a la meta x factor de caída, donde
factor = 1 + (caída desde el máximo de 52 semanas / volatilidad anual) / vol_step, con tope.
Se compran hasta max_buys fondos (al menos uno del bloque principal), con un mínimo por compra.
"""
import numpy as np
import pandas as pd
from config import (DATA, RESULTS, TARGET, CORE, SIM_SERIES, SCV_MIX, MONTHLY, FEE, RULE)

p = pd.read_csv(DATA / "precios.csv", index_col=0, parse_dates=True).ffill()
px = pd.DataFrame({k: p[v] for k, v in SIM_SERIES.items()})
r = p[list(SCV_MIX)].pct_change()
px["scv"] = (1 + sum(r[k] * w for k, w in SCV_MIX.items())).cumprod()
px = px[list(TARGET)].loc["2020-06-01":]
W = pd.Series(TARGET)

high = px.rolling(252, min_periods=200).max()
dd = (1 - px / high) * 100                                              # caída desde el máximo, en %
vol = px.pct_change().rolling(252, min_periods=200).std() * np.sqrt(252) * 100   # volatilidad anual, en %

month_ends = [d for d in px.resample("ME").last().index if d >= pd.Timestamp("2021-09-30")]
dates = [px.index[px.index <= d][-1] for d in month_ends]


def allocate(hold, cash, d, mode, max_buys, min_ticket, step):
    total = hold.sum() + cash
    deficit = W * total - hold
    if mode == "none":
        factor = pd.Series(1.0, index=W.index)
    elif mode == "raw":
        factor = (1 + dd.loc[d] / step).clip(upper=RULE["cap"])
    else:  # "vol": caída medida en volatilidades
        factor = (1 + (dd.loc[d] / vol.loc[d]) / step).clip(upper=RULE["cap"])
    score = (deficit.clip(lower=0) * factor)
    score = score[score > 0].sort_values(ascending=False)
    for k in range(min(max_buys, len(score)), 0, -1):
        chosen = list(score.index[:k])
        if not CORE & set(chosen):
            core = [x for x in score.index if x in CORE]
            if core:
                chosen = chosen[:k - 1] + [core[0]]
        investable = cash - FEE * len(chosen)
        amounts = investable * score[chosen] / score[chosen].sum()
        if (amounts >= min_ticket).all() or k == 1:
            return amounts


def run(mode="vol", max_buys=RULE["max_buys"], min_ticket=RULE["min_ticket"], step=RULE["vol_step"],
        pro_rata=False, fees=True):
    hold = pd.Series(0.0, index=W.index)
    paid, prev, deviation = 0.0, None, []
    for d in dates:
        if prev is not None:
            hold = hold * (px.loc[d] / px.loc[prev])
        if pro_rata:
            f = FEE * len(W) if fees else 0.0
            amounts = (MONTHLY - f) * W
        else:
            amounts = allocate(hold, MONTHLY, d, mode, max_buys, min_ticket, step)
            f = FEE * len(amounts)
        paid += f
        hold[amounts.index] += amounts
        deviation.append((hold / hold.sum() - W).abs().sum() / 2 * 100)
        prev = d
    return hold, paid, np.mean(deviation[12:])


def irr(final, n):
    lo, hi = -0.5, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        fv = sum(MONTHLY * (1 + mid) ** ((n - i - 1) / 12) for i in range(n))
        lo, hi = (lo, mid) if fv > final else (mid, hi)
    return mid * 100


variants = {
    "Reparto exacto, sin comisiones (teórico)": dict(pro_rata=True, fees=False),
    "Reparto exacto en los 10 fondos": dict(pro_rata=True),
    "Una compra por mes al mayor déficit": dict(mode="none", max_buys=1, min_ticket=0),
    "Hasta 3 compras, solo déficit": dict(mode="none"),
    "Hasta 3 compras, caída cruda (/20)": dict(mode="raw", step=20),
    "Hasta 3 compras, caída / volatilidad (regla elegida)": dict(mode="vol", step=1),
    "Hasta 2 compras, caída / volatilidad": dict(mode="vol", step=1, max_buys=2),
}
rows = []
for name, kw in variants.items():
    hold, paid, dev = run(**kw)
    rows.append({"estrategia": name, "valor_final": hold.sum(), "tir_%": irr(hold.sum(), len(dates)),
                 "comisiones": paid, "desvio_promedio_%": dev})
res = pd.DataFrame(rows).set_index("estrategia").round(2)
print(f"{dates[0].date()} a {dates[-1].date()}, {len(dates)} meses, aportado {len(dates) * MONTHLY:,.0f}")
print(res.to_string())
res.to_csv(RESULTS / "backtest_reglas.csv")

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
