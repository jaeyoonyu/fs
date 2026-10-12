"""Re-render the pages from the data already inside them, after a change to
shell.py or a template, without downloading anything from the SEC again.

Run from the repo root:  python scripts/rebuild.py
"""
import re
from pathlib import Path

import home
from shell import ROOT, write_page

HERE = Path(__file__).resolve().parent


def body_of(slug):
    s = (ROOT / slug / "index.html").read_text(encoding="utf-8")
    return re.search(r"<main>\n<h1>[^<]*</h1>\n(.*)\n</main>", s, re.S).group(1)


def stamp_of(body):
    return re.search(r"updated (\d{4}-\d\d-\d\d \d\d:\d\d)", body).group(1)


def main():
    write_page("fundamentals", "Fundamentals", body_of("fundamentals"))   # no template: keep the body
    b = body_of("ratios")
    data = re.search(r"const DATA = (\[.*?\]);\n", b).group(1)
    page = (HERE / "ratios_template.html").read_text(encoding="utf-8")
    write_page("ratios", "Ratios", page.replace("__DATA__", data).replace("__STAMP__", stamp_of(b)))
    b = body_of("statements")
    m = re.search(r"const DATA = (\[.*?\]), LAYOUT = (\{.*?\});\n", b)
    page = (HERE / "statements_template.html").read_text(encoding="utf-8")
    write_page("statements", "Statements", page.replace("__DATA__", m.group(1))
               .replace("__LAYOUT__", m.group(2)).replace("__STAMP__", stamp_of(b)))
    home.main()
    print("rebuilt")


if __name__ == "__main__":
    main()
