"""Build ratios.md: quarterly margins, current ratio, NI vs. OCF, FCF, shares
outstanding, and public float per ticker.

Run from the repo root:  python scripts/ratios.py
Data: SEC EDGAR companyfacts API (the XBRL numbers each company tags in its
10-Qs and 10-Ks). Flows reported only as year-to-date or annual totals are
turned into quarters by differencing: Q = YTD - prior YTD of the same year.
Cover-page share counts filed per share class are missing from companyfacts,
so for those companies they are read from each filing's own XBRL instance.
"""
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from fundamentals import GROUPS, UA, doc_url, fye_mmdd, get_json, month_end
from shell import write_page

FIRST_COL, LAST_COL = (2019, 1), (2026, 2)  # calendar quarters shown, (year, q)
TAGS = {
    "rev": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax",
            "RevenuesNetOfInterestExpense"],
    "gp": ["GrossProfit"],
    "cost": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"],
    "ni": ["NetIncomeLoss", "ProfitLoss"],
    "oi": ["OperatingIncomeLoss"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
              "PaymentsForCapitalImprovements"],
    "ca": ["AssetsCurrent"],
    "cl": ["LiabilitiesCurrent"],
    # Delta stopped tagging a capex total in 2026; its two parts add up to it.
    "flight": ["PaymentsForFlightEquipment"],
    "other_pp": ["PaymentsToAcquireOtherProductiveAssets"],
}
INSTANT = {"ca", "cl"}


def days(start, end):
    return (datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days


def facts_for(gaap, tag):
    """[(start or None, end, value)] for one tag in USD, the latest filing winning."""
    out = {}
    facts = gaap.get(tag, {}).get("units", {}).get("USD", [])
    for f in sorted(facts, key=lambda f: f["filed"]):
        if f.get("form", "").startswith(("10-K", "10-Q")):
            out[(f.get("start"), f["end"])] = f["val"]
    return out


def flow_quarters(vals):
    """end -> (value, derived). Direct 12-16 week quarters first; otherwise the
    difference between consecutive year-to-date totals that share a start date."""
    out = {e: (v, False) for (s, e), v in vals.items() if s and 75 <= days(s, e) <= 120}
    by_start = {}
    for (s, e), v in vals.items():
        if s and days(s, e) <= 380:
            by_start.setdefault(s, []).append((e, v))
    for s, ytd in by_start.items():
        ytd.sort()
        for (e0, v0), (e1, v1) in zip(ytd, ytd[1:]):
            if 75 <= days(e0, e1) <= 120 and e1 not in out:
                out[e1] = (v1 - v0, True)
    return out


def instants(vals):
    return {e: (v, False) for (s, e), v in vals.items() if s is None}


def best(gaap, key):
    """Merge a metric's tags, preferring the one whose data runs latest."""
    conv = instants if key in INSTANT else flow_quarters
    series = [s for s in (conv(facts_for(gaap, t)) for t in TAGS[key]) if s]
    series.sort(key=lambda s: (max(s), len(s)), reverse=True)
    merged = {}
    for s in reversed(series):
        merged.update(s)
    return merged


def instance_shares(cik, acc, doc):
    """Cover-page shares summed over share classes, from the filing's XBRL instance."""
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/"
    try:  # inline XBRL filings (mid-2019 on) ship an extracted <doc>_htm.xml
        x = fetch_text(base + re.sub(r"\.htm$", "_htm.xml", doc))
    except urllib.error.HTTPError:  # older filings: the one .xml that is not a linkbase
        names = [i["name"] for i in get_json(base + "index.json")["directory"]["item"]]
        inst = [n for n in names if n.endswith(".xml") and not re.search(r"_(cal|def|lab|pre)\.xml$|FilingSummary", n)]
        x = fetch_text(base + inst[0])
    vals = re.findall(r"<dei:EntityCommonStockSharesOutstanding\b[^>]*>\s*([\d.]+)\s*<", x)
    return sum(float(v) for v in vals) if vals else None


def fetch_text(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read().decode("utf-8", "replace")


def shares_by_period(cik, dei, filings):
    """period end -> (shares, cover date) from each 10-K/10-Q cover page."""
    out = {}
    for f in dei.get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares", []):
        if f["accn"] in filings:
            period = filings[f["accn"]]["reportDate"]
            v, _ = out.get(period, (0, None))
            out[period] = (v + f["val"], f["end"])  # several classes -> several facts
    # Classes filed only with a dimension never reach companyfacts: read those filings.
    for acc, f in filings.items():
        if f["reportDate"] not in out:
                try:
                    v = instance_shares(cik, acc, f["primaryDocument"])
                except Exception as e:
                    print("  no instance", acc, e)
                    continue
                if v:
                    out[f["reportDate"]] = (v, f["filingDate"])
                time.sleep(0.15)
    return out


def filing_index(sub):
    """accession -> filing row, for every 10-K/10-Q in the window."""
    # "recent" holds only the last 1,000 filings; heavy filers' older 10-Qs are in extra files.
    blocks = [sub["filings"]["recent"]] + [
        get_json(f"https://data.sec.gov/submissions/{f['name']}")
        for f in sub["filings"].get("files", []) if f["filingTo"] >= f"{FIRST_COL[0]}-01-01"]
    return {r["accessionNumber"]: r for b in blocks for r in (dict(zip(b, v)) for v in zip(*b.values()))
            if r["form"] in ("10-K", "10-Q") and r["reportDate"] >= f"{FIRST_COL[0] - 1}-12-01"}


def filing_urls(cik, filings):
    """period end -> URL of the filing's main document (the original if amended),
    opened in SEC's inline XBRL viewer when the filing supports it."""
    return {f["reportDate"]: doc_url(cik, acc, f["primaryDocument"], f.get("isInlineXBRL"))
            for acc, f in sorted(filings.items(), key=lambda kv: kv[1]["filingDate"], reverse=True)}


def company(cik, sub, ticker):
    facts = get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")
    gaap = facts["facts"].get("us-gaap", {})
    dei = facts["facts"].get("dei", {})
    m = {k: best(gaap, k) for k in TAGS}
    filings = filing_index(sub)
    shares = shares_by_period(cik, dei, filings)
    doc_url = filing_urls(cik, filings)
    floats = {}
    for f in sorted(dei.get("EntityPublicFloat", {}).get("units", {}).get("USD", []), key=lambda f: f["filed"]):
        floats[f["end"]] = f["val"]
    rows = []
    for e in sorted(set(m["rev"]) & set(m["ni"]), reverse=True):
        val = lambda k: m[k][e][0] if e in m[k] else None
        gp = val("gp")
        if gp is None and val("cost") is not None:
            gp = val("rev") - val("cost")
        capex = val("capex")
        if capex is None and val("flight") is not None and val("other_pp") is not None:
            capex = val("flight") + val("other_pp")
        me = month_end(datetime.strptime(e, "%Y-%m-%d").date())
        rows.append(dict(end=e, col=me.year * 4 + (me.month - 1) // 3,
                         derived=m["rev"][e][1] or m["ni"][e][1],
                         rev=val("rev"), gp=gp, oi=val("oi"), ni=val("ni"), ocf=val("ocf"),
                         capex=capex, ca=val("ca"), cl=val("cl"),
                         shares=shares.get(e, (None,))[0],
                         shares_asof=shares.get(e, (None, None))[1],
                         float=None, float_asof=None, url=doc_url.get(e)))
    # Same column rule as the Fundamentals page: a long first quarter that lands
    # in the next filing's quarter moves back one column.
    for newer, r in zip(rows, rows[1:]):
        if r["col"] >= newer["col"]:
            r["col"] = newer["col"] - 1
    # Public float is measured once a year (end of the second fiscal quarter);
    # it goes in the column of that measurement date.
    by_col = {r["col"]: r for r in rows}
    for asof, v in floats.items():
        me = month_end(datetime.strptime(asof, "%Y-%m-%d").date())
        r = by_col.get(me.year * 4 + (me.month - 1) // 3)
        if r:
            r["float"], r["float_asof"] = v, asof
    lo = FIRST_COL[0] * 4 + FIRST_COL[1] - 1
    hi = LAST_COL[0] * 4 + LAST_COL[1] - 1
    rows = [r for r in reversed(rows) if lo <= r["col"] <= hi]
    for r in rows:
        r["q"] = f"{(r['col'] // 4) % 100:02d}Q{r['col'] % 4 + 1}"
        del r["col"]
    return facts["entityName"], rows, split_adjust(rows, ticker)


# Splits the ratio test gets wrong, as (quarter first seen, ratio). FuelCell's
# 1-for-12 (May 2019) came with heavy issuance, so it looks like 1-for-5.
SPLIT_OVERRIDE = {"FCEL": {"19Q2": 1 / 12}}


def split_adjust(rows, ticker):
    """Restate earlier share counts for stock splits. A forward split is a jump
    between consecutive cover counts within 3% of a standard ratio. A reverse split
    gets 12%, because the companies doing them often issue shares the same quarter
    (FuelCell's 1-for-30 shows up as 1-for-27)."""
    standard = [2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 35, 40, 50, 100]
    splits = []
    for r in rows:
        r["shares_raw"] = r["shares"]  # as filed; the page can toggle back to it
    have = [r for r in rows if r["shares"]]
    for old, new in zip(have, have[1:]):
        ratio = new["shares"] / old["shares"]
        k, tol = None, 0
        if ratio >= 1.8:
            k, tol = min(standard, key=lambda s: abs(ratio / s - 1)), 0.03
        elif ratio <= 0.55:  # issuance only shrinks the apparent ratio, so snap upward
            up = [s for s in standard if s >= 1 / ratio * 0.97]
            k, tol = (1 / up[0], 0.12) if up else (None, 0)
        k = SPLIT_OVERRIDE.get(ticker, {}).get(new["q"], k)
        if new["q"] in SPLIT_OVERRIDE.get(ticker, {}):
            tol = float("inf")  # known split: take it as given
        if k and abs(ratio / k - 1) < tol:
            splits.append((new["q"], k))
            for r in rows[:rows.index(new)]:
                if r["shares"]:
                    r["shares"] *= k
                    r["shares_adj"] = True
    return [f"{q}: {k:g}-for-1" if k > 1 else f"{q}: 1-for-{1 / k:g}" for q, k in splits]


def pe(mcap, ttm_ni, cap=200):
    if not mcap or not ttm_ni or ttm_ni <= 0 or mcap / ttm_ni > cap:
        return None
    return round(mcap / ttm_ni, 1)


def add_valuation(c):
    """Quarter-end close, market cap, and P/E, plus the same as of the latest close.

    Prices come from FinanceDataReader (Yahoo Finance) at build time; only these
    derived numbers are published, never the daily series. Yahoo's Close is
    split-adjusted, so market cap = Close x split-adjusted cover shares stays on
    one basis across splits, and P/E = market cap / trailing-four-quarter net
    income avoids mixing pre- and post-split EPS. P/E is left blank when trailing
    earnings are zero or negative, or so small that P/E tops 200 (not meaningful).
    """
    import FinanceDataReader as fdr
    rows = c["quarters"]
    try:
        px = fdr.DataReader(c["ticker"], f"{FIRST_COL[0] - 1}-12-01")["Close"].dropna()
    except Exception as e:
        print("  no prices", c["ticker"], e)
        px = None
    for i, r in enumerate(rows):
        last4 = rows[max(0, i - 3):i + 1]
        r["ttm_ni"] = sum(q["ni"] for q in last4) if len(last4) == 4 else None
        before = px[px.index <= r["end"]] if px is not None else []
        r["px"] = round(float(before.iloc[-1]), 2) if len(before) else None
        r["mcap"] = r["px"] * r["shares"] if r["px"] and r["shares"] else None
        r["pe"] = pe(r["mcap"], r["ttm_ni"])
    last = rows[-1]
    if px is not None and len(px):
        now = dict(px=round(float(px.iloc[-1]), 2), date=px.index[-1].strftime("%Y-%m-%d"))
        now["mcap"] = now["px"] * last["shares"] if last["shares"] else None
        now["pe"] = pe(now["mcap"], last["ttm_ni"])
        c["now"] = now
    else:
        c["now"] = None


def main():
    root = Path(__file__).resolve().parent.parent
    tickmap = {v["ticker"]: v["cik_str"]
               for v in get_json("https://www.sec.gov/files/company_tickers.json").values()}
    data = []
    for group, tickers in GROUPS:
        for t in tickers:
            sub = get_json(f"https://data.sec.gov/submissions/CIK{tickmap[t]:010d}.json")
            name, rows, splits = company(tickmap[t], sub, t)
            fye = fye_mmdd(sub.get("fiscalYearEnd") or "1231")
            exch = {"Nasdaq": "NASDAQ", "NYSE": "NYSE"}.get((sub.get("exchanges") or [""])[0], "")
            data.append(dict(ticker=t, name=name, group=group, fye=fye, exchange=exch,
                             splits=splits, quarters=rows))
            add_valuation(data[-1])
            if splits:
                print("  split-adjusted", t, splits)
            r = rows[-1]
            miss = [k for k in ("gp", "ocf", "capex", "ca", "cl", "shares")
                    if sum(q[k] is None for q in rows) > 0]
            gpm = f"{r['gp'] / r['rev']:.1%}" if r["gp"] is not None else "-"
            cr = f"{r['ca'] / r['cl']:.2f}" if r["ca"] and r["cl"] else "-"
            print(f"{t:6} n={len(rows)} {r['q']} GPM {gpm} NPM {r['ni'] / r['rev']:.1%} CR {cr}"
                  f" shares {r['shares']} floats {sum(q['float'] is not None for q in rows)}"
                  f"  P/E now {(data[-1]['now'] or {}).get('pe')}  missing:{miss}")
            time.sleep(0.25)
    order = [g for g, _ in GROUPS]
    data.sort(key=lambda c: (order.index(c["group"]), c["fye"], c["ticker"]))

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    page = (Path(__file__).with_name("ratios_template.html").read_text(encoding="utf-8")
            .replace("__DATA__", json.dumps(data, separators=(",", ":")))
            .replace("__STAMP__", stamp))
    write_page("ratios", "Ratios", page)


if __name__ == "__main__":
    main()
