"""Build statements.md: a standardized balance sheet and income statement per
ticker and quarter, next to the same quarter a year earlier.

Run from the repo root:  python scripts/statements.py
Data: SEC EDGAR companyfacts API, as on the Ratios page. Each 10-Q/10-K is one
period. Income-statement amounts are for the quarter (Q4 = annual - nine-month
year-to-date); balance-sheet amounts are at the period end.

Standardized: every company's XBRL tags are mapped onto one template, so the
lines are not each company's own presentation. Lines a company does not tag are
gathered into an "Other ..." line per section (subtotal minus the lines shown),
so each section adds up to its subtotal and assets = liabilities + equity.
"""
import json
import time
from datetime import datetime
from pathlib import Path

from fundamentals import GROUPS, fye_mmdd, get_json, month_end
from shell import write_page
from ratios import FIRST_COL, LAST_COL, TAGS as RATIO_TAGS, facts_for, filing_index, filing_urls, \
    flow_quarters, instants

# Tagged lines: (key, tags, kind). kind: "bs" instant, "is" quarterly flow.
TAGGED = [
    # Target, Lululemon, Papa John's tag cash only with restricted cash included.
    ("cash", ["CashAndCashEquivalentsAtCarryingValue", "Cash",
              "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"], "bs"),
    ("sti", ["ShortTermInvestments", "MarketableSecuritiesCurrent",
             "AvailableForSaleSecuritiesDebtSecuritiesCurrent", "DebtSecuritiesCurrent"], "bs"),
    ("ar", ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"], "bs"),
    ("inv", ["InventoryNet"], "bs"),
    ("ca", ["AssetsCurrent"], "bs"),
    ("ppe", ["PropertyPlantAndEquipmentNet",
             "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization"], "bs"),
    ("rou", ["OperatingLeaseRightOfUseAsset"], "bs"),
    ("gw", ["Goodwill"], "bs"),
    ("intang", ["IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsNet"], "bs"),
    ("ta", ["Assets"], "bs"),
    ("ap", ["AccountsPayableCurrent", "AccountsPayableTradeCurrent"], "bs"),
    ("accr", ["AccruedLiabilitiesCurrent"], "bs"),
    ("std", ["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings"], "bs"),
    ("cl", ["LiabilitiesCurrent"], "bs"),
    ("ltd", ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"], "bs"),
    ("oll", ["OperatingLeaseLiabilityNoncurrent"], "bs"),
    ("tl", ["Liabilities"], "bs"),
    ("csapic", ["CommonStocksIncludingAdditionalPaidInCapital"], "bs"),
    ("cs", ["CommonStockValue"], "bs"),
    ("apic", ["AdditionalPaidInCapitalCommonStock", "AdditionalPaidInCapital"], "bs"),
    ("re", ["RetainedEarningsAccumulatedDeficit"], "bs"),
    ("treas_pos", ["TreasuryStockValue", "TreasuryStockCommonValue"], "bs"),
    ("aoci", ["AccumulatedOtherComprehensiveIncomeLossNetOfTax"], "bs"),
    ("se", ["StockholdersEquity"], "bs"),
    ("nci", ["MinorityInterest"], "bs"),
    ("te", ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"], "bs"),
    ("tle", ["LiabilitiesAndStockholdersEquity"], "bs"),
    ("rev", RATIO_TAGS["rev"], "is"),
    ("cogs", RATIO_TAGS["cost"], "is"),
    ("gp", ["GrossProfit"], "is"),
    ("rd", ["ResearchAndDevelopmentExpense"], "is"),
    ("sga", ["SellingGeneralAndAdministrativeExpense"], "is"),
    ("oi", ["OperatingIncomeLoss"], "is"),
    ("int", ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"], "is"),
    ("pti", ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
             "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"], "is"),
    ("tax", ["IncomeTaxExpenseBenefit"], "is"),
    ("ni", RATIO_TAGS["ni"], "is"),
]

# What the page shows, in order: (key, label, style). style: "#" section heading,
# "sub" detail line, "oth" computed remainder, "tot" subtotal/total, "" plain.
BS_LAYOUT = [
    ("#", "Assets", "#"),
    ("cash", "Cash & equivalents", "sub"), ("sti", "Short-term investments", "sub"),
    ("ar", "Accounts receivable", "sub"), ("inv", "Inventory", "sub"),
    ("oca", "Others", "oth"), ("ca", "Total current assets", "tot"),
    ("ppe", "PP&E, net", "sub"), ("rou", "Lease right-of-use assets", "sub"),
    ("gw", "Goodwill", "sub"), ("intang", "Intangibles, net", "sub"),
    ("onca", "Others", "oth"), ("ta", "Total assets", "tot"),
    ("#", "Liabilities", "#"),
    ("ap", "Accounts payable", "sub"), ("accr", "Accrued liabilities", "sub"),
    ("std", "Short-term debt", "sub"),
    ("ocl", "Others", "oth"), ("cl", "Total current liab.", "tot"),
    ("ltd", "Long-term debt", "sub"), ("oll", "Lease liabilities", "sub"),
    ("oncl", "Others", "oth"), ("tl", "Total liabilities", "tot"),
    ("mezz", "Mezzanine equity", "oth"),
    ("#", "Equity", "#"),
    ("paid", "Paid-in capital", "sub"), ("re", "Retained earnings", "sub"),
    ("treas", "Treasury stock", "sub"), ("aoci", "AOCI", "sub"),
    ("oeq", "Others", "oth"), ("se", "Shareholders' equity", "tot"),
    ("nci", "Noncontrolling int.", "sub"), ("te", "Total equity", "tot"),
    ("tle", "Total liab. & equity", "tot"),
]
IS_LAYOUT = [
    ("rev", "Revenue", "tot"), ("cogs", "Cost of revenue", "sub"), ("gp", "Gross profit", "tot"),
    ("rd", "R&D expense", "sub"), ("sga", "SG&A expense", "sub"),
    ("oopex", "Others", "oth"), ("oi", "Operating income", "tot"),
    ("int", "Interest expense", "sub"), ("onon", "Others", "oth"),
    ("pti", "Pretax income", "tot"), ("tax", "Income tax", "sub"),
    ("oni", "Others", "oth"),
    ("ni", "Net income", "tot"), ("eps", "EPS (diluted)", ""),
]
LAYOUT_KEYS = [k for k, _, s in BS_LAYOUT + IS_LAYOUT if s != "#"]


def merged(gaap, tags, conv):
    """Merge tags, preferring the one whose data runs latest (as on the Ratios page)."""
    series = [s for s in (conv(facts_for(gaap, t)) for t in tags) if s]
    series.sort(key=lambda s: (max(s), len(s)), reverse=True)
    out = {}
    for s in reversed(series):
        out.update(s)
    return out


def eps_quarters(gaap):
    """Diluted EPS for directly reported quarters only: annual minus nine-month EPS
    is not a valid Q4 EPS (the share counts differ), so derived quarters are left out."""
    out = {}
    for f in sorted(gaap.get("EarningsPerShareDiluted", {}).get("units", {}).get("USD/shares", []),
                    key=lambda f: f["filed"]):
        if f.get("start") and f.get("form", "").startswith(("10-K", "10-Q")):
            d = (datetime.strptime(f["end"], "%Y-%m-%d") - datetime.strptime(f["start"], "%Y-%m-%d")).days
            if 75 <= d <= 120:
                out[f["end"]] = f["val"]
    return out


def rest(total, *parts):
    """Subtotal minus the parts that are shown; None when the subtotal is unknown."""
    if total is None:
        return None
    r = total - sum(p for p in parts if p is not None)
    return 0 if abs(r) < 5e5 else r  # rounding noise below $0.5M shows as 0


def fill(v):
    """Totals a company leaves untagged, then the "Other ..." remainders."""
    if v["gp"] is None and v["rev"] is not None and v["cogs"] is not None:
        v["gp"] = v["rev"] - v["cogs"]
    if v["te"] is None and v["se"] is not None:
        v["te"] = v["se"] + (v["nci"] or 0)
    if v["se"] is None and v["te"] is not None:
        v["se"] = v["te"] - (v["nci"] or 0)
    # Many companies tag no total-liabilities line: it is then L&E minus equity
    # (which folds any mezzanine equity into liabilities).
    v["tl_derived"] = v["tl"] is None and v["tle"] is not None and v["te"] is not None
    if v["tl_derived"]:
        v["tl"] = v["tle"] - v["te"]
    v["paid"] = v["csapic"] if v["csapic"] is not None else (
        None if v["cs"] is None and v["apic"] is None else (v["cs"] or 0) + (v["apic"] or 0))
    v["treas"] = -v["treas_pos"] if v["treas_pos"] else None  # a deduction from equity
    v["oca"] = rest(v["ca"], v["cash"], v["sti"], v["ar"], v["inv"])
    v["onca"] = rest(None if v["ta"] is None or v["ca"] is None else v["ta"] - v["ca"],
                     v["ppe"], v["rou"], v["gw"], v["intang"])
    v["ocl"] = rest(v["cl"], v["ap"], v["accr"], v["std"])
    v["oncl"] = rest(None if v["tl"] is None or v["cl"] is None else v["tl"] - v["cl"], v["ltd"], v["oll"])
    v["mezz"] = rest(None if v["tle"] is None or v["tl"] is None or v["te"] is None else v["tle"] - v["tl"] - v["te"]) or None
    v["oeq"] = rest(v["se"], v["paid"], v["re"], v["treas"], v["aoci"])
    base = v["gp"] if v["gp"] is not None else v["rev"]
    v["oopex"] = None if v["oi"] is None or base is None else rest(base - v["oi"], v["rd"], v["sga"])
    v["onon"] = None if v["pti"] is None or v["oi"] is None else rest(v["pti"] - v["oi"] + (v["int"] or 0))
    v["oni"] = None if v["pti"] is None or v["tax"] is None or v["ni"] is None else rest(v["ni"] - v["pti"] + v["tax"])
    return v


def company(cik, sub):
    facts = get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")
    gaap = facts["facts"].get("us-gaap", {})
    m = {k: merged(gaap, tags, instants if kind == "bs" else flow_quarters) for k, tags, kind in TAGGED}
    eps = eps_quarters(gaap)
    filings = filing_index(sub)
    urls = filing_urls(cik, filings)
    tenk = {f["reportDate"] for f in filings.values() if f["form"] == "10-K"}
    rows = []
    for e in sorted({f["reportDate"] for f in filings.values()}, reverse=True):
        v = {k: (m[k][e][0] if e in m[k] else None) for k, *_ in TAGGED}
        if v["ta"] is None and v["rev"] is None:
            continue
        derived = any(m[k][e][1] for k, _, kind in TAGGED if kind == "is" and e in m[k])
        v = fill(v)
        v["eps"] = None if derived else eps.get(e)
        me = month_end(datetime.strptime(e, "%Y-%m-%d").date())
        rows.append(dict(end=e, col=me.year * 4 + (me.month - 1) // 3, url=urls.get(e),
                         form="10-K" if e in tenk else "10-Q", derived=derived, **v))
    # Same column rule as the other pages: a long first quarter that lands in the
    # next filing's quarter moves back one column.
    for newer, r in zip(rows, rows[1:]):
        if r["col"] >= newer["col"]:
            r["col"] = newer["col"] - 1
    lo, hi = FIRST_COL[0] * 4 + FIRST_COL[1] - 1, LAST_COL[0] * 4 + LAST_COL[1] - 1
    rows = [r for r in reversed(rows) if lo <= r["col"] <= hi]
    for r in rows:
        r["q"] = f"{(r['col'] // 4) % 100:02d}Q{r['col'] % 4 + 1}"
    return facts["entityName"], rows


def main():
    root = Path(__file__).resolve().parent.parent
    tickmap = {v["ticker"]: v["cik_str"]
               for v in get_json("https://www.sec.gov/files/company_tickers.json").values()}
    data = []
    for group, tickers in GROUPS:
        for t in tickers:
            sub = get_json(f"https://data.sec.gov/submissions/CIK{tickmap[t]:010d}.json")
            name, rows = company(tickmap[t], sub)
            data.append(dict(ticker=t, name=name, group=group, fye=fye_mmdd(sub.get("fiscalYearEnd") or "1231"),
                             quarters=rows))
            r = rows[-1]
            gap = None if r["ta"] is None or r["tl"] is None or r["te"] is None else \
                round((r["ta"] - r["tl"] - (r["mezz"] or 0) - r["te"]) / 1e6)
            print(f"{t:6} n={len(rows)} {r['q']} A-(L+M+E)={gap}M tl_derived={r['tl_derived']}"
                  f" other: oca={r['oca'] and round(r['oca'] / 1e6)} onca={r['onca'] and round(r['onca'] / 1e6)}"
                  f" oeq={r['oeq'] and round(r['oeq'] / 1e6)} mezz={r['mezz'] and round(r['mezz'] / 1e6)}")
            time.sleep(0.25)
    order = [g for g, _ in GROUPS]
    data.sort(key=lambda c: (order.index(c["group"]), c["fye"], c["ticker"]))
    # Compact rows: the amounts become one list in LAYOUT_KEYS order (about half the size),
    # and filing URLs drop their common prefix, which the page adds back.
    base = "https://www.sec.gov/Archives/edgar/data/"
    for c in data:
        c["quarters"] = [dict(q=r["q"], end=r["end"], form=r["form"], derived=r["derived"],
                              tl_derived=r["tl_derived"], u=(r["url"] or "").replace(base, ""),
                              v=[r[k] for k in LAYOUT_KEYS]) for r in c["quarters"]]
    layout = dict(keys=LAYOUT_KEYS,
                  bs=[dict(key=k, label=lab, style=s) for k, lab, s in BS_LAYOUT],
                  is_=[dict(key=k, label=lab, style=s) for k, lab, s in IS_LAYOUT])

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    page = (Path(__file__).with_name("statements_template.html").read_text(encoding="utf-8")
            .replace("__DATA__", json.dumps(data, separators=(",", ":")))
            .replace("__LAYOUT__", json.dumps(layout, separators=(",", ":")))
            .replace("__STAMP__", stamp))
    write_page("statements", "Statements", page)


if __name__ == "__main__":
    main()
