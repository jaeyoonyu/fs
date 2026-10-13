# Financials: financial statements from SEC filings

https://jaeyoonyu.github.io/fs/

Fundamentals, ratios, and financial statements of US companies, built from public SEC EDGAR data
(data.sec.gov). Quarter-end stock prices for P/E come from Yahoo Finance via FinanceDataReader; only
quarter-end closes, market cap, and P/E are published. The price chart is an embedded TradingView widget.

| Page | Built by |
|---|---|
| `fundamentals/` | `scripts/fundamentals.py` |
| `ratios/` | `scripts/ratios.py` (+ `ratios_template.html`) |
| `statements/` | `scripts/statements.py` (+ `statements_template.html`) and `scripts/statements_full.py` → `assets/statements/*.json` |
| `methods/` | `scripts/methods.py` |
| `index.html` | `scripts/home.py` |

Tickers and sectors are set in `GROUPS` in `scripts/fundamentals.py`.

`.github/workflows/site.yml` reruns all scripts every Monday and publishes the site; it can also be
started by hand from the Actions tab. SEC downloads are cached in `scripts/cache/` (not in git).

After changing `shell.py` or a template, `python scripts/rebuild.py` re-renders the pages from the data
already in them (no SEC downloads).

To refresh by hand, from the repo root:

```
python scripts/fundamentals.py
python scripts/ratios.py
python scripts/statements.py
python scripts/statements_full.py
python scripts/home.py
python scripts/methods.py
```
