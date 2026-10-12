"""The page shell shared by every FS page: header, tabs, colors.

Each generator builds its page body and calls write_page(); the result is a
plain static file (<slug>/index.html) served by GitHub Pages as-is.
"""
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABS = [("fundamentals", "Fundamentals"), ("ratios", "Ratios"), ("statements", "Statements")]

HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{tab_title}</title>
<meta name="description" content="Fundamentals, ratios, and financial statements of US companies, built from SEC EDGAR filings.">
<style>
:root {{ --bg: #ffffff; --ink: #1c2321; --muted: #5c6863; --line: #e0e5e0; --acc: #2a78d6; --background: #ffffff; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #17191c; --ink: #e6e8ea; --muted: #9aa1a8; --line: #2c3036; --acc: #5598e7; --background: #17191c; }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--ink);
  font-family: "Segoe UI", -apple-system, "Helvetica Neue", Roboto, sans-serif; line-height: 1.5; }}
a {{ color: var(--acc); }}
.fs-top {{ display: flex; align-items: center; gap: 22px; flex-wrap: wrap; padding: 10px 24px;
  border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 5; background: var(--bg); }}
.fs-brand {{ font-weight: 800; font-size: 18px; color: inherit; text-decoration: none; letter-spacing: .02em; }}
.fs-brand small {{ font-weight: 400; color: var(--muted); font-size: 12px; margin-left: 6px; }}
.fs-tabs {{ display: flex; gap: 4px; }}
.fs-tabs a {{ padding: 5px 14px; border-radius: 999px; color: inherit; text-decoration: none; font-size: 14px; }}
.fs-tabs a:hover {{ background: rgba(128,128,128,.12); }}
.fs-tabs a.on {{ background: var(--acc); color: #fff; }}
.fs-home {{ margin-left: auto; font-size: 13px; color: var(--muted); text-decoration: none; }}
main {{ padding: 16px 24px 40px; max-width: 1480px; margin: 0 auto; }}
main h1 {{ font-size: 22px; margin: 4px 0 12px; }}
@media (max-width: 600px) {{ .fs-top, main {{ padding-left: 16px; padding-right: 16px; }} }}
</style>
</head>
<body>
<header class="fs-top">
  <a class="fs-brand" href="{base}">Financials<small>from SEC filings</small></a>
  <nav class="fs-tabs">{tabs}</nav>
  <a class="fs-home" href="https://jaeyoonyu.github.io/">Jaeyoon Yu ↗</a>
</header>
<main>
<h1>{title}</h1>
"""
FOOT = """
</main>
</body>
</html>
"""


def write_page(slug, title, body):
    """slug "" is the landing page at the site root; the others live one folder down."""
    base = "./" if not slug else "../"
    tabs = "".join(f'<a href="{base}{s}/" class="{"on" if s == slug else ""}">{t}</a>' for s, t in TABS)
    out = ROOT / slug / "index.html" if slug else ROOT / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    tab_title = title if not slug else f"{title} · Financials"
    out.write_text(HEAD.format(title=title, tab_title=tab_title, tabs=tabs, base=base) + body + FOOT, encoding="utf-8")


def stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M")
