"""Build fundamentals.md: per-ticker links + 10-K/10-Q filings since 2024 by calendar quarter.

Run from the repo root:  python scripts/fundamentals.py
Data: SEC EDGAR submissions API (filing list) + companyfacts API (fiscal
year/period each company tagged on its own filing, i.e. its own convention).
"""
import json
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path

from shell import write_page

UA = {"User-Agent": "Jaeyoon Yu yu10j@cmich.edu"}
FIRST_COL, LAST_COL = (2024, 1), (2026, 2)  # calendar quarters shown, (year, q)

# (group, [tickers]). Competitors added: CAVA (SG), CMCSA (CHTR), EVGO and BLNK
# (CHPT), BE and FCEL (PLUG), SEDG (ENPH).
GROUPS = [
    ("Tech", ["MU", "NVDA", "GOOGL", "AMZN", "AVGO", "ORCL", "NFLX"]),
    ("Retail", ["WMT", "COST", "KR", "TGT", "TJX"]),
    ("Footwear / apparel", ["NKE", "CROX", "DECK", "LULU"]),
    ("Restaurants", ["SG", "CAVA", "DPZ", "PZZA", "YUM", "DRI"]),
    ("Autos / used cars", ["KMX", "CVNA", "GM", "F"]),
    ("Airlines", ["UAL", "DAL", "AAL", "LUV"]),
    ("Cruise lines", ["RCL", "CCL", "NCLH"]),
    ("Cable / broadband", ["CHTR", "CMCSA"]),
    ("EV charging", ["CHPT", "EVGO", "BLNK"]),
    ("Hydrogen / fuel cells", ["PLUG", "BE", "FCEL"]),
    ("Solar inverters", ["ENPH", "SEDG"]),
]


def get_json(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2)


def month_end(d):
    """Date snapped to the nearest month end (2026-02-01 -> 2026-01-31)."""
    y, mm = d.year, d.month
    if d.day <= 15:
        y, mm = (y - 1, 12) if mm == 1 else (y, mm - 1)
    return date(y + (mm == 12), mm % 12 + 1, 1) - date.resolution


def fye_mmdd(fye):
    """EDGAR's MMDD fiscal year end as the nearest month end (0201 -> 0131)."""
    return month_end(date(2025, int(fye[:2]), int(fye[2:]))).strftime("%m%d")


def filing_fy_fp(cik):
    """accn -> (fy, fp) from the DEI focus the company reported on that filing."""
    facts = get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")
    out = {}
    for taxo in facts.get("facts", {}).values():
        for concept in taxo.values():
            for unit in concept.get("units", {}).values():
                for f in unit:
                    if f.get("form") in ("10-K", "10-Q") and f.get("fy") and f.get("fp"):
                        out.setdefault(f["accn"], (f["fy"], f["fp"]))
    return out


def company(ticker, cik):
    sub = get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    recent = sub["filings"]["recent"]
    rows = [dict(zip(recent, vals)) for vals in zip(*recent.values())]
    rows = [r for r in rows if r["form"] in ("10-K", "10-Q") and r["reportDate"]]
    for r in rows:
        r["end"] = month_end(datetime.strptime(r["reportDate"], "%Y-%m-%d").date())
    rows = [r for r in rows if r["end"] >= date(FIRST_COL[0] - 1, 10, 1)]  # trimmed in main
    fye = sub.get("fiscalYearEnd") or "1231"
    # The tagged fy is noisy filing to filing, so it only votes on the company's
    # naming convention (fiscal year named for the year it ends vs. starts);
    # every label is then computed from the period-end date.
    tagged = filing_fy_fp(cik)
    computed = {r["accessionNumber"]: fiscal_end_and_q(r["reportDate"], fye) for r in rows}
    votes = [tagged[a][0] - e.year for a, (e, _) in computed.items() if a in tagged]
    offset = max(set(votes), key=votes.count) if votes else 0
    filings = []
    for r in rows:
        end, q = computed[r["accessionNumber"]]
        fy = end.year + offset
        if r["form"] == "10-K":
            q = 4
        url = (f"https://www.sec.gov/Archives/edgar/data/{cik}/"
               f"{r['accessionNumber'].replace('-', '')}/{r['primaryDocument']}")
        e = r["end"]
        filings.append(dict(form=r["form"], period=r["reportDate"], filed=r["filingDate"],
                            label=f"{fy % 100:02d}Q{q}", url=url,
                            text=("A" if r["form"] == "10-K" else "Q") + e.strftime("%m%d"),
                            col=e.year * 4 + (e.month - 1) // 3))
        tag = tagged.get(r["accessionNumber"])
        if tag and (tag[0] != fy or tag[1] not in (f"Q{q}", "FY")):
            print(f"  note {ticker} {r['reportDate']}: tagged {tag}, using {fy}Q{q}")
    return dict(ticker=ticker, cik=cik, name=sub["name"], fye=fye, filings=filings)


def fiscal_end_and_q(period, fye):
    """(end date of the fiscal year containing period, fiscal quarter 1-4)."""
    d = datetime.strptime(period, "%Y-%m-%d").date()
    mm, dd = int(fye[:2]), min(int(fye[2:]), 28)
    # 52/53-week years drift a few days around the nominal FYE, hence the 10-day slack.
    end = min(e for e in (date(y, mm, dd) for y in range(d.year - 1, d.year + 2))
              if (e - d).days >= -10)
    return end, 4 - round((end - d).days / 91.3)


def main():
    root = Path(__file__).resolve().parent.parent
    tickmap = {v["ticker"]: v["cik_str"]
               for v in get_json("https://www.sec.gov/files/company_tickers.json").values()}
    data = []
    for group, tickers in GROUPS:
        for t in tickers:
            c = company(t, tickmap[t])
            c["group"] = group
            data.append(c)
            print(t, c["fye"], [f["label"] for f in c["filings"]])
            time.sleep(0.25)

    # Columns are calendar quarters, oldest first; a filing sits in the quarter
    # its period end (snapped to month end) falls in.
    # A long first quarter (CAVA's 16 weeks to late April) can land in the same
    # quarter as the next filing; then the earlier one moves back a column.
    for c in data:
        c["filings"].sort(key=lambda f: f["period"], reverse=True)
        for newer, f in zip(c["filings"], c["filings"][1:]):
            if f["col"] >= newer["col"]:
                print(f"  shift {c['ticker']} {f['period']} back one quarter")
                f["col"] = newer["col"] - 1
    lo, hi = (FIRST_COL[0] * 4 + FIRST_COL[1] - 1, LAST_COL[0] * 4 + LAST_COL[1] - 1)
    cols = list(range(lo, hi + 1))
    # Within a sector, order by fiscal year end, then ticker.
    data.sort(key=lambda c: ([g for g, _ in GROUPS].index(c["group"]), fye_mmdd(c["fye"]), c["ticker"]))

    def colname(k):
        return f"{(k // 4) % 100:02d}Q{k % 4 + 1}"

    th = "".join(f"<th>{colname(k)}</th>" for k in cols)
    body = []
    group = None
    for c in data:
        if c["group"] != group:
            group = c["group"]
            body.append(f'<tr class="grp"><td colspan="{3 + len(cols)}">{group}</td></tr>')
        t = c["ticker"]
        by_col = {f["col"]: f for f in c["filings"]}
        cells = []
        for k in cols:
            f = by_col.get(k)
            if not f:
                cells.append("<td></td>")
                continue
            cls = ' class="k"' if f["form"] == "10-K" else ""
            tip = (f'{f["form"]} &middot; fiscal {f["label"]} &middot; period {f["period"]}'
                   f' &middot; filed {f["filed"]}')
            cells.append(f'<td{cls}><a href="{f["url"]}" target="_blank" title="{tip}">{f["text"]}</a></td>')
        body.append(
            f'<tr><td class="tk" title="{c["name"]}">{t}</td><td>{fye_mmdd(c["fye"])}</td>'
            f'<td class="lk"><a href="https://stockanalysis.com/stocks/{t.lower()}/" target="_blank">SA</a>'
            f' | <a href="https://finviz.com/quote.ashx?t={t}" target="_blank">FV</a>'
            f' | <a href="https://www.sec.gov/edgar/browse/?CIK={c["cik"]}" target="_blank">SEC</a></td>'
            + "".join(cells) + "</tr>")

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    md = f"""<style>
.fund-wrap {{ overflow-x: auto; }}
table.fund {{ border-collapse: collapse; font-size: 12px; white-space: nowrap; margin: 0 auto; }}
table.fund th, table.fund td {{ padding: 2px 5px; border-bottom: 1px solid rgba(128,128,128,.25); text-align: center; }}
table.fund th {{ position: sticky; top: 52px; background: var(--background, #fff); font-weight: 600; }}
table.fund td.tk {{ text-align: left; font-weight: 700; padding-left: 14px; }}
table.fund td.lk {{ opacity: .85; }}
table.fund tr.grp td {{ text-align: left; font-weight: 700; padding-top: 8px; opacity: .7; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; }}
table.fund td.k a {{ font-weight: 700; }}
table.fund td.k, .fund-notes .k {{ background: rgba(255,214,0,.4); }}
.fund-notes {{ font-size: 13px; margin-top: .8em; padding-left: 1.2em; }}
.fund-notes li {{ margin: 1px 0; }}
.fund-notes .k {{ padding: 0 3px; font-weight: 700; }}
table.fund th:nth-child(3), table.fund td:nth-child(3) {{ border-right: 1px solid rgba(128,128,128,.4); }}
</style>

<div class="fund-wrap">
<table class="fund">
<thead><tr><th>Ticker</th><th>FYE</th><th>Links</th>{th}</tr></thead>
<tbody>
{chr(10).join(body)}
</tbody>
</table>
</div>

<ul class="fund-notes">
<li><b>SA</b> = stockanalysis.com</li>
<li><b>FV</b> = finviz.com</li>
<li><b>SEC</b> = the company's filing list on SEC EDGAR</li>
<li><b>FYE</b> = fiscal year end (MMDD)</li>
<li><b>Q0731</b> = 10-Q, quarter ending July 31</li>
<li><span class="k">A0131</span> = 10-K (annual report), year ending January 31</li>
<li>Columns = calendar quarters, oldest → newest</li>
<li>Dates are rounded to the nearest month end</li>
<li>Click a cell to open the filing; hover for the exact date and the company's own fiscal quarter</li>
<li>Updated {stamp} from SEC EDGAR</li>
</ul>
"""
    write_page("fundamentals", "Fundamentals", md)


if __name__ == "__main__":
    main()
