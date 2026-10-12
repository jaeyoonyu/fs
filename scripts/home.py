"""Build index.html, the landing page.  Run from the repo root:  python scripts/home.py"""
from fundamentals import GROUPS
from shell import write_page

CARDS = [
    ("fundamentals", "Fundamentals",
     "Every company's 10-Q and 10-K filings since 2024 by calendar quarter, with links to StockAnalysis, Finviz, and EDGAR."),
    ("ratios", "Ratios",
     "Profit margins, current ratio, cash flows, shares, public float, P/E, and stock price, quarter by quarter since 2019; "
     "click a sector to compare its companies."),
    ("statements", "Statements",
     "The balance sheet and income statement of any company and quarter, exactly as filed with the SEC or standardized, "
     "with definitions for every line."),
]


def main():
    n = sum(len(t) for _, t in GROUPS)
    cards = "".join(f'<a class="card" href="./{slug}/"><b>{title} →</b><span>{text}</span></a>' for slug, title, text in CARDS)
    body = f"""<style>
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; max-width: 980px; }}
.card {{ display: flex; flex-direction: column; gap: 6px; padding: 16px 18px; border: 1px solid var(--line); border-radius: 10px;
  color: inherit; text-decoration: none; }}
.card:hover {{ border-color: var(--acc); }}
.card b {{ font-size: 17px; color: var(--acc); }}
.card span {{ color: var(--muted); font-size: 14px; }}
.lead {{ color: var(--muted); max-width: 760px; margin: 0 0 18px; }}
</style>
<p class="lead">{n} US companies in {len(GROUPS)} sectors, built from public SEC EDGAR filings (data.sec.gov) and refreshed weekly.
For teaching introductory financial accounting and financial statement analysis.</p>
<div class="cards">{cards}</div>
"""
    write_page("", "Financials", body)


if __name__ == "__main__":
    main()
