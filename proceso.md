---
title: El proceso en Python
---

# El proceso en Python

Cómo se pasó de más de 4.500 ETFs a una cartera de 10, con código que cualquiera puede ejecutar. [Volver a la metodología](./)

Todo el código está en la carpeta [`python/`](https://github.com/alejitovm97-byte/Screener-ETFs/tree/main/python) del repositorio, en dos formatos: cinco scripts numerados y un notebook listo para Google Colab ([abrir en Colab](https://colab.research.google.com/github/alejitovm97-byte/Screener-ETFs/blob/main/python/metodologia_etf.ipynb)). Los parámetros (fondos, pesos, umbrales) están en `config.py`, así que para probar una variante alcanza con cambiar ese archivo.

| Paso | Script | Qué hace | Resultado |
|---|---|---|---|
| 1 | `01_universo.py` | Baja la tabla completa de ETFs de justETF | `data/universo_justetf.csv` |
| 2 | `02_screener.py` | Filtros duros, casilleros y ranking de eficiencia | `resultados/ranking_eficiencia.csv` |
| 3 | `03_precios.py` | Historia de precios de la lista corta y de los proxies | `data/precios.csv` |
| 4 | `04_metricas.py` | Rendimientos de 1 a 10 años, volatilidad, caída máxima, Sharpe | `resultados/metricas.csv` |
| 5 | `05_backtest.py` | Simulación de la regla de compra mensual | `resultados/backtest_reglas.csv` |

Las fuentes son públicas: justETF, a través de la librería no oficial [justetf-scraping](https://github.com/druzsan/justetf-scraping), y Yahoo Finance, a través de `yfinance`. Los datos descargados no se publican en el repositorio; cada persona los baja al ejecutar el código, así que los resultados cambian según la fecha.

## Paso 1: el universo

Una sola llamada devuelve todos los ETFs con su índice, domicilio, política de dividendos, TER, tamaño, rendimientos a 1, 3 y 5 años, rendimientos por año calendario, volatilidad y caída máxima:

```python
import justetf_scraping
df = justetf_scraping.load_overview()   # más de 4.500 ETFs
```

## Paso 2: filtros, normalización y ranking

Primero, los filtros duros que definen el universo elegible:

```python
u = u[(u.domicile_country == "Ireland") & (u.dividends == "Accumulating")
      & (~u.hedged) & (u.strategy != "Short & Leveraged")]      # 4.589 -> 1.480 fondos
```

Después, cada casillero de índice puro se arma por nombre del índice, excluyendo variantes que no lo replican tal cual (ESG, factoriales, coberturas con opciones) y fondos de menos de 100 millones.

**Normalización por percentil.** Dentro de cada casillero, cada criterio se convierte en su posición relativa, de 0 (el peor) a 100 (el mejor). La primera versión usaba la distancia entre el mejor y el peor, pero eso estiraba diferencias mínimas: en emergentes, 1,6 puntos de rendimiento acumulado a 3 años se convertían en un ranking con saltos grandes. Rankear por posición es más robusto.

```python
def percentile(s, higher_is_better=True):
    r = s.rank(ascending=higher_is_better, method="average")
    n = s.notna().sum()
    return (r - 1) / (n - 1) * 100
```

**Puntaje:** seguimiento del índice 40% (percentil del rendimiento a 1 y 3 años contra los demás fondos del mismo índice, que mide el costo real y no solo el declarado), costo 20%, tamaño 20% e historia 20%.

**Empates:** si la diferencia de rendimiento anualizado a 3 años contra el mejor es menor a 0,3 puntos, se considera empate, porque por debajo de eso la diferencia se explica más por el momento en que se mide el precio que por la calidad del fondo.

Resultado en el casillero del Nasdaq 100:

| Fondo | TER | 1 año | 3 años | Puntaje | Empate con el mejor |
|---|---|---|---|---|---|
| BNP Paribas Easy II Nasdaq 100 | 0,14% | 29,7% | 96,1% | 77 | sí |
| UBS Nasdaq-100 | 0,13% | 29,5% | s/d | 57 | s/d |
| Invesco Nasdaq-100 Swap | 0,20% | 29,5% | 96,0% | 55 | sí |
| Xtrackers Nasdaq 100 | 0,20% | 29,4% | 95,5% | 53 | sí |
| iShares Nasdaq 100 (CNDX) | 0,30% | 29,3% | 94,9% | 45 | sí |

Y en emergentes, donde el ranking muestra sobre todo que los fondos son intercambiables:

| Fondo | TER | 1 año | 3 años | Puntaje | Empate con el mejor |
|---|---|---|---|---|---|
| UBS MSCI EM SF | 0,14% | 36,8% | 80,4% | 66 | sí |
| SPDR MSCI Emerging Markets | 0,18% | 35,0% | 80,5% | 58 | sí |
| Invesco MSCI Emerging Markets | 0,09% | 35,1% | 78,8% | 54 | no |
| iShares MSCI EM | 0,18% | 35,0% | 80,3% | 53 | sí |
| HSBC MSCI Emerging Markets | 0,15% | 35,3% | 79,0% | 43 | no |

Rendimientos acumulados en euros según justETF, septiembre de 2026.

**Lo que el ranking no hace.** Las estrategias factoriales (small cap value, EM Value) y los temáticos no pasan por este puntaje: rankear estrategias distintas por rendimiento pasado es elegir lo que más subió. Esas decisiones se tomaron con la historia completa de precios (pasos 3 y 4), la evidencia académica y el análisis de cada tesis.

## Paso 3: historia de precios

Para la lista corta, la historia completa desde justETF; para los ciclos largos, ETFs estadounidenses equivalentes desde Yahoo Finance:

```python
df = justetf_scraping.load_chart("IE00BG0SKF03", currency="USD")        # EM Value
h = yf.Ticker("AVUV").history(period="max", auto_adjust=True)["Close"]  # Avantis SCV EE.UU.
```

Los fondos de acumulación reinvierten dividendos, así que su precio ya es rendimiento total; en los estadounidenses se usa el precio ajustado.

## Paso 4: métricas

Para cada serie se calculan rendimientos anualizados a 1, 2, 3, 4, 5, 7 y 10 años (cuando hay historia), volatilidad y Sharpe a 5 años con letras del Tesoro (BIL) como tasa libre de riesgo, caída máxima y rendimientos por año calendario. Fue la base de decisiones como elegir EM Value: al separar sus rendimientos año por año se vio que le ganó al índice en 5 de 7 años completos, y que sin el último año su ventaja (unos 3 puntos anuales) era similar a la de Avantis.

## Paso 5: la regla de compra

La regla, en pocas líneas:

```python
deficit = W * (cartera.sum() + aporte) - cartera                         # cuánto le falta a cada fondo
factor = (1 + (caida_52s / volatilidad_anual) / vol_step).clip(upper=3)  # caída medida en volatilidades
prioridad = deficit.clip(lower=0) * factor
# se compran hasta 3 fondos de mayor prioridad, en proporción a la prioridad,
# con al menos uno del bloque principal y un mínimo de USD 250 por compra
```

Simulación con aportes de USD 1.000 por mes entre octubre de 2021 y septiembre de 2026 (61 meses) y USD 2 de comisión por compra:

| Estrategia | Valor final | TIR | Comisiones | Desvío promedio de la meta |
|---|---|---|---|---|
| Reparto exacto, sin comisiones (teórico) | USD 104.233 | 21,85% | 0 | 3,7% |
| Reparto exacto en los 10 fondos | USD 102.148 | 21,01% | USD 1.220 | 3,7% |
| Una compra por mes al mayor déficit | USD 104.586 | 21,99% | USD 122 | 6,2% |
| Hasta 3 compras, solo déficit | USD 104.504 | 21,96% | USD 290 | 1,8% |
| Hasta 3 compras, caída cruda | USD 104.336 | 21,89% | USD 268 | 2,1% |
| Hasta 3 compras, caída / volatilidad (regla elegida) | USD 104.731 | 22,05% | USD 276 | 2,1% |
| Hasta 2 compras, caída / volatilidad | USD 104.178 | 21,83% | USD 238 | 2,4% |

La regla no resta rendimiento frente al reparto perfecto, ahorra comisiones y mantiene la cartera cerca de la meta. Las variantes difieren en décimas: el ajuste por caída ordena las compras, no genera rendimiento extra.

## Cómo reproducirlo

En Google Colab, abrí el notebook y ejecutá las celdas en orden. En tu computadora:

```bash
pip install -r requirements.txt
cd python
python 01_universo.py
python 02_screener.py
python 03_precios.py
python 04_metricas.py
python 05_backtest.py
```

Dos advertencias: `justetf-scraping` es una librería no oficial que puede dejar de funcionar si cambia el sitio, y conviene usarla con moderación (el paso 3 espera un segundo y medio entre fondos). Los resultados de las simulaciones usan fondos equivalentes con más historia y tienen el sesgo de haber elegido los fondos conociendo su desempeño reciente.

> Material educativo; no constituye asesoramiento de inversión.
