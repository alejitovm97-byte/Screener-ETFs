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
