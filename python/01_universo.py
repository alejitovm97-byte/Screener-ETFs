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
