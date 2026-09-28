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
