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
