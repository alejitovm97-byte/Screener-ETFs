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
