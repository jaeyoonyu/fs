"""Collect the full, as-filed balance sheet, income statement, and cash flow statement of every 10-Q/10-K
for the Statements page's "Full version": assets/statements/<TICKER>.json.

Run from the repo root:  python scripts/statements_full.py
Data: SEC EDGAR. Each XBRL filing lists its statements in FilingSummary.xml and
renders each one as a small HTML table (R2.htm, R4.htm, ...). Those tables keep
the company's own line items, labels, and comparison columns. Downloads are
cached in _code/cache/ (git-ignored), so a rerun only fetches new filings.
"""
import html
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from fundamentals import GROUPS, UA, get_json
from ratios import FIRST_COL, filing_index
from statements import company as simple_company

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).with_name("cache") / "sec"
OUT = ROOT / "assets" / "statements"

# Which report is which: matched on the report's short name in FilingSummary.xml.
FIND = {
    "is": re.compile(r"(statements?|statement) of (consolidated )?(income|operations|earnings)|income statements?"
                     r"|statements? of (comprehensive )?\(?(income|loss)|operations", re.I),  # "(Loss) Income" too
    "bs": re.compile(r"balance sheets?|financial (condition|position)", re.I),
    "cf": re.compile(r"cash flows?", re.I),
}
SKIP = re.compile(r"parenthetical|details|policies|tables|narrative", re.I)


def fetch(url):
    """GET with a disk cache; SEC asks for at most 10 requests per second."""
    path = CACHE / re.sub(r"[^\w.-]", "_", url.split("/edgar/data/")[-1])
    if path.exists():
        return path.read_text(encoding="utf-8")
    time.sleep(0.12)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        text = r.read().decode("utf-8", "replace")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def pick_reports(summary):
    """{'is': 'R4.htm', 'bs': 'R2.htm'}: the first matching statement of each kind."""
    reports = re.findall(r"<Report\b.*?</Report>", summary, re.S)
    out = {}
    for rep in reports:
        short = re.search(r"<ShortName>(.*?)</ShortName>", rep, re.S)
        fname = re.search(r"<HtmlFileName>(.*?)</HtmlFileName>", rep, re.S)
        cat = re.search(r"<MenuCategory>(.*?)</MenuCategory>", rep, re.S)
        # Early-2022 10-Ks file some statements as "Uncategorized" (after the new audit-information page).
        if not (short and fname) or (cat and cat.group(1).strip() not in ("Statements", "Uncategorized")):
            continue
        name = html.unescape(short.group(1)).strip()
        if SKIP.search(name):
            continue
        for kind, rx in FIND.items():
            # Prefer a statement of income over one of comprehensive income.
            if kind not in out and rx.search(name) and not (kind == "is" and "comprehensive" in name.lower()
                                                           and "and comprehensive" not in name.lower()):
                out[kind] = (fname.group(1).strip(), name)
    if "is" not in out:  # some companies only file a combined comprehensive-income statement
        for rep in reports:
            short = re.search(r"<ShortName>(.*?)</ShortName>", rep, re.S)
            fname = re.search(r"<HtmlFileName>(.*?)</HtmlFileName>", rep, re.S)
            if short and fname and FIND["is"].search(short.group(1)) and not SKIP.search(short.group(1)):
                out["is"] = (fname.group(1).strip(), html.unescape(short.group(1)).strip())
                break
    return out


def text(cell):
    return html.unescape(re.sub(r"<[^>]+>", " ", cell)).replace("\xa0", " ").strip()


def parse_report(page):
    """{'title', 'unit', 'heads': [[period group, date], ...], 'rows': [[label, kind, v1, v2, ...]]}
    kind: 1 = section heading (bold in the filing), 2 = total (underlined), 0 = other."""
    rows = re.findall(r"<tr\b([^>]*)>(.*?)</tr>", page, re.S)
    head_cells, rows_out, title, unit = [], [], "", ""
    for attrs, body in rows:
        ths = re.findall(r"<th\b([^>]*)>(.*?)</th>", body, re.S)
        if ths:
            if not title:
                t = text(ths[0][1]).split(" - ")
                title, unit = t[0].strip(), (t[1].strip() if len(t) > 1 else "")
            head_cells.append(ths if not head_cells else ths)
            continue
        tds = re.findall(r"<td\b([^>]*)>(.*?)</td>", body, re.S)
        if not tds or "pl" not in tds[0][0]:
            continue
        label = text(tds[0][1])
        if not label or label.endswith("[Abstract]"):  # generic XBRL root headings, e.g. "Income Statement [Abstract]"
            continue
        cls = re.search(r'class="(\w+)"', attrs)
        kind = 1 if "<strong>" in tds[0][1] else 2 if cls and cls.group(1).endswith("u") else 0
        vals = [re.sub(r"^\$\s*", "", text(c)) for _, c in tds[1:]]
        rows_out.append([label, kind] + vals)
    # Column headings: the first header row spans period groups ("3 Months Ended"),
    # the second gives the dates; a single header row means dates only.
    heads = []
    if len(head_cells) >= 2:
        groups = []
        for attrs, c in head_cells[0][1:]:
            span = int((re.search(r'colspan="(\d+)"', attrs) or [None, 1])[1])
            groups += [text(c)] * span
        dates = [text(c) for _, c in head_cells[1]]
        heads = [[g, d] for g, d in zip(groups, dates)]
    elif head_cells:
        heads = [["", text(c)] for _, c in head_cells[0][1:]]
    return dict(title=title, unit=unit, heads=heads, rows=rows_out)


def filing_statements(cik, acc):
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/"
    try:
        reports = pick_reports(fetch(base + "FilingSummary.xml"))
    except urllib.error.HTTPError:
        return {}
    out = {}
    for kind, (fname, name) in reports.items():
        try:
            out[kind] = parse_report(fetch(base + fname))
        except urllib.error.HTTPError:
            pass
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tickmap = {v["ticker"]: v["cik_str"]
               for v in get_json("https://www.sec.gov/files/company_tickers.json").values()}
    for _, tickers in GROUPS:
        for t in tickers:
            cik = tickmap[t]
            sub = get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
            filings = filing_index(sub)
            # The quarters the simple version shows, so both versions agree on labels.
            _, rows = simple_company(cik, sub)
            q_of = {r["end"]: r["q"] for r in rows}
            data, missing = {}, []
            for acc, f in sorted(filings.items(), key=lambda kv: kv[1]["filingDate"]):
                q = q_of.get(f["reportDate"])
                if not q:
                    continue
                st = filing_statements(cik, acc)
                if st:
                    data[q] = dict(form=f["form"], **st)
                if any(k not in st for k in ("bs", "is", "cf")):
                    missing.append(f"{q}:{','.join(k for k in ('bs', 'is', 'cf') if k not in st)}")
            (OUT / f"{t}.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
            print(f"{t:6} {len(data)} quarters  missing: {missing or '-'}", flush=True)


if __name__ == "__main__":
    main()
