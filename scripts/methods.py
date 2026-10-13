"""Build methods/index.html: where the data comes from and how it is handled.

Run from the repo root:  python scripts/methods.py
Plain content; edit the text below when a method changes.
"""
from fundamentals import GROUPS
from shell import write_page

BODY = """<style>
.md {{ max-width: 900px; font-size: 15px; }}
.md h2 {{ font-size: 18px; margin: 26px 0 6px; padding-top: 8px; border-top: 1px solid var(--line); }}
.md h2:first-of-type {{ border-top: 0; margin-top: 4px; }}
.md ul {{ margin: 4px 0 8px; padding-left: 1.3em; }}
.md li {{ margin: 2px 0; }}
.md code {{ font-size: 13px; background: rgba(128,128,128,.14); padding: 1px 5px; border-radius: 4px; }}
.md table {{ border-collapse: collapse; font-size: 14px; margin: 6px 0 10px; }}
.md th, .md td {{ text-align: left; padding: 4px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }}
.md th {{ font-weight: 600; }}
.md .muted {{ color: var(--muted); }}
.md nav.toc {{ display: flex; gap: 6px 14px; flex-wrap: wrap; font-size: 14px; margin-bottom: 8px; }}
</style>
<div class="md">

<nav class="toc">
  <a href="#sources">Sources</a><a href="#quarters">Quarters</a><a href="#statements">Statements</a>
  <a href="#ratios">Ratios</a><a href="#shares">Shares &amp; P/E</a><a href="#refresh">Refresh</a>
  <a href="#limits">Limitations</a>
</nav>

<h2 id="sources">Where the data comes from</h2>
<table>
<tr><th>Data</th><th>Source</th></tr>
<tr><td>List of 10-Q/10-K filings, filing dates, fiscal year end</td>
    <td>SEC EDGAR submissions API (<code>data.sec.gov/submissions</code>)</td></tr>
<tr><td>Financial statement amounts (revenue, net income, assets, cash flows, …)</td>
    <td>SEC XBRL company facts API (<code>data.sec.gov/api/xbrl/companyfacts</code>): the numbers each company tags in its own filings</td></tr>
<tr><td>Statements "as filed"</td>
    <td>The SEC's rendering of each filing's statements (the <code>R</code> pages listed in its <code>FilingSummary.xml</code>)</td></tr>
<tr><td>Shares outstanding</td>
    <td>The cover page of each 10-Q/10-K (XBRL <code>dei:EntityCommonStockSharesOutstanding</code>), read from the filing itself when a company tags it by share class</td></tr>
<tr><td>Public float</td><td>The 10-K cover page (<code>dei:EntityPublicFloat</code>)</td></tr>
<tr><td>Quarter-end stock prices (for P/E and market cap)</td>
    <td>Yahoo Finance via FinanceDataReader, fetched at each refresh; only quarter-end closes, market cap, and P/E are published</td></tr>
<tr><td>Stock price chart</td><td>An embedded TradingView widget; it loads in your browser and nothing is stored here</td></tr>
</table>
<ul>
<li>{n} companies in {g} sectors; the list is set by hand.</li>
<li>No licensed databases (Compustat, CRSP, I/B/E/S, …) are used.</li>
<li>StockAnalysis and Finviz appear only as links.</li>
</ul>

<h2 id="quarters">Quarters and dates</h2>
<ul>
<li>Every 10-Q and 10-K is one period, identified by its period end date.</li>
<li>Columns are <b>calendar quarters</b>: the period end is rounded to the nearest month end and placed in that month's quarter.</li>
<li>So a fiscal quarter ending Jan 31 (e.g., NVIDIA, Walmart) sits in calendar Q1.</li>
<li>If a long first quarter (16 weeks, e.g., CAVA) lands in the same calendar quarter as the next filing, the earlier one moves back a column.</li>
<li>Hover a quarter for the exact period end and the company's own fiscal quarter label.</li>
<li>Fiscal labels follow each company's convention (fiscal year named for the year it ends or starts), taken from the fiscal year the company tags in its filings.</li>
</ul>

<h2 id="statements">Statement amounts</h2>
<ul>
<li><b>Q4</b>: a 10-K reports only the full year, so Q4 = annual minus the nine-month year-to-date amount; these quarters are marked <b>*</b>.</li>
<li><b>Cash flows</b> are filed year-to-date, so each quarter = year-to-date minus the prior year-to-date.</li>
<li><b>Balance sheet</b> amounts are as of the period end; nothing is derived.</li>
<li>When a company uses different XBRL tags for the same line (e.g., <code>Revenues</code> vs. <code>RevenueFromContractWithCustomerExcludingAssessedTax</code>), the tag with the most recent data is used and older quarters are filled from the others.</li>
<li>EPS for Q4 is left blank: annual EPS minus nine-month EPS is not a valid quarterly EPS, because the share counts differ.</li>
</ul>

<h2>As filed vs. standardized statements</h2>
<ul>
<li><b>As filed (SEC)</b>: the company's own statements, with its own lines, labels, and comparison columns, exactly as in the filing.</li>
<li><b>Standardized</b>: every company's tags mapped onto one template, so companies can be compared line by line.</li>
<li>In the standardized version, lines a company does not tag go into <i>Others</i>, computed as the subtotal minus the lines shown, so every section adds up.</li>
<li>When a company reports no total-liabilities line, it is computed as total liabilities and equity minus total equity (marked †).</li>
<li>Redeemable (mezzanine) equity, when present, is shown between liabilities and equity.</li>
<li>The accounting equation (assets = liabilities + equity) is checked for every quarter.</li>
<li>In the standardized cash flow statement, payments (capex, dividends, buybacks) are shown as negatives.</li>
</ul>

<h2 id="ratios">Ratios</h2>
<table>
<tr><th>Ratio</th><th>Definition</th></tr>
<tr><td>Gross / operating / net profit margin</td><td>Gross profit / operating income / net income ÷ revenue</td></tr>
<tr><td>Current ratio</td><td>Current assets ÷ current liabilities, at the quarter end</td></tr>
<tr><td>Free cash flow (FCF)</td><td>Cash from operations − capital expenditures</td></tr>
<tr><td>OCF and FCF margin</td><td>Cash from operations or FCF ÷ revenue</td></tr>
<tr><td>Cash conversion</td><td>Cash from operations ÷ net income; n/m when net income ≤ 0 or the multiple tops 20×</td></tr>
<tr><td>P/E</td><td>Market cap ÷ net income of the last four quarters; n/m when that income ≤ 0 or P/E tops 200×</td></tr>
</table>
<ul>
<li>Net income is net income attributable to the company (excluding noncontrolling interests).</li>
<li>Gross profit is the tagged gross profit, or revenue minus cost of revenue; airlines, cable companies, and others that report neither show "not filed".</li>
<li>In sector comparisons, margins beyond ±100% are drawn at the chart's edge; tooltips and tables show the actual values.</li>
</ul>

<h2 id="shares">Shares, splits, and P/E</h2>
<ul>
<li>Shares outstanding = all share classes on the cover page, as of a date shortly after the quarter end.</li>
<li>Stock splits are detected where the count jumps by a standard ratio (×2, ×10, ÷20, …) between quarters; earlier counts are restated to the post-split basis.</li>
<li>One split is set by hand: FuelCell Energy's 1-for-12 in 2019, which came with heavy share issuance.</li>
<li>Market cap = quarter-end closing price × split-adjusted shares outstanding.</li>
<li>Prices are already split-adjusted, so working from market cap keeps P/E on one basis across splits.</li>
<li>Public float is measured once a year (end of the second fiscal quarter) and is placed in that quarter.</li>
</ul>

<h2 id="refresh">Refresh</h2>
<ul>
<li>Every Monday a GitHub Actions job reruns all the scripts and publishes the site.</li>
<li>New filings appear within a week; the SEC usually adds a filing's XBRL data within a day or two of filing.</li>
<li>The scripts and the workflow are public: <a href="https://github.com/jaeyoonyu/fs">github.com/jaeyoonyu/fs</a>.</li>
</ul>

<h2 id="limits">Limitations</h2>
<ul>
<li>The data is only as good as each company's XBRL tagging; tagging errors and changes of tags carry through.</li>
<li>When a company stops tagging a line, the standardized version moves that amount into <i>Others</i>.</li>
<li>Derived quarters (Q4, cash flows) can differ slightly from figures a company reports elsewhere, e.g., after restatements.</li>
<li>Gaps: a few filings have no rendered statements (e.g., Sweetgreen's first 10-K, 21Q4), and the latest quarter can lag when the SEC has not yet posted a filing's XBRL data.</li>
<li>For teaching and research only; not investment advice.</li>
</ul>
<p class="muted">Questions or errors: <a href="mailto:yu10j@cmich.edu">yu10j@cmich.edu</a></p>
</div>
"""


def main():
    write_page("methods", "Data & methods",
               BODY.format(n=sum(len(t) for _, t in GROUPS), g=len(GROUPS)))


if __name__ == "__main__":
    main()
