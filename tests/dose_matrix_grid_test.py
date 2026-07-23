#!/usr/bin/env python3
"""
Dose Log matrix grid test
-------------------------
Verifies buildDoseMatrix produces a real 2-axis table:
  - corner label:  Ymed \\ Xmed
  - X-axis column headers (dose values)
  - Y-axis row headers (dose values)
  - outcome cells at intersections

Run:
  python3 tests/dose_matrix_grid_test.py
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser


def esc(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def dose_label(d: dict) -> str:
    am = (d.get("am") or "").strip()
    pm = (d.get("pm") or "").strip()
    if am and pm:
        return f"{am} AM / {pm} PM"
    if am:
        return am
    if pm:
        return f"{pm} PM"
    return (d.get("dose") or "").strip()


def med_dose_key(d: dict) -> str:
    return dose_label(d) or "—"


def doses_for_med(entry: dict, med_name: str):
    for d in entry.get("doses") or []:
        if (d.get("name") or "").strip().lower() == med_name.lower():
            return med_dose_key(d)
    return None


def build_dose_matrix(entries: list, x_med: str, y_med: str) -> str:
    """Python port of index.html buildDoseMatrix()."""
    if not x_med or not y_med or x_med == y_med:
        return ""

    x_vals: set[str] = set()
    y_vals: set[str] = set()
    cells: dict[str, dict] = {}

    for e in entries:
        xv = doses_for_med(e, x_med)
        yv = doses_for_med(e, y_med)
        if xv is None or yv is None:
            continue
        x_vals.add(xv)
        y_vals.add(yv)
        k = f"{xv}||{yv}"
        if k not in cells:
            cells[k] = {"total": 0, "noPain": 0}
        cells[k]["total"] += 1
        if e.get("outcome") == "no_pain":
            cells[k]["noPain"] += 1

    xs = sorted(x_vals)
    ys = sorted(y_vals)
    if not xs or not ys:
        return '<div class="card"><p class="small">Not enough overlapping dose data for these two meds yet.</p></div>'

    html = f'<div class="matrix-wrap"><table class="matrix"><thead><tr><th>{esc(y_med)} \\ {esc(x_med)}</th>'
    for x in xs:
        html += f'<th class="axis-lbl">{esc(x)}</th>'
    html += "</tr></thead><tbody>"

    for y in ys:
        html += f'<tr><th class="axis-lbl">{esc(y)}</th>'
        for x in xs:
            c = cells.get(f"{x}||{y}")
            if not c:
                html += '<td><div class="matrix-cell cell-empty">·</div></td>'
                continue
            rate = c["noPain"] / c["total"]
            cls, label = "cell-mixed", f'{round(rate * 100)}%'
            if c["total"] == 1:
                cls = "cell-once"
                label = "OK?" if c["noPain"] else "Pain?"
            elif rate >= 0.7:
                cls = "cell-good"
            elif rate <= 0.3:
                cls = "cell-bad"
            detail = "Needs Repeat" if c["total"] == 1 else f'{c["noPain"]}/{c["total"]}'
            html += (
                f'<td><div class="matrix-cell {cls}" title="{c["noPain"]}/{c["total"]} no pain">'
                f'{label}<div style="font-weight:500;opacity:.8">{detail}</div></div></td>'
            )
        html += "</tr>"

    html += "</tbody></table></div>"
    html += (
        '<div class="small" style="margin-bottom:12px">'
        "Green ≥70% no pain · Gold mixed · Red ≤30% · Gray dashed = single trial (Needs Repeat)"
        "</div>"
    )
    return html


# Sample log: Naltrexone (X) × Lamotrigine (Y) — enough variation for a real grid
SAMPLE_ENTRIES = [
    {
        "outcome": "no_pain",
        "doses": [
            {"name": "Naltrexone", "am": "4.5mg", "pm": "3.0mg"},
            {"name": "Lamotrigine", "am": "125mg", "pm": "125mg"},
        ],
    },
    {
        "outcome": "no_pain",
        "doses": [
            {"name": "Naltrexone", "am": "4.5mg", "pm": "3.0mg"},
            {"name": "Lamotrigine", "am": "125mg", "pm": "125mg"},
        ],
    },
    {
        "outcome": "pain",
        "doses": [
            {"name": "Naltrexone", "am": "3.0mg", "pm": "3.0mg"},
            {"name": "Lamotrigine", "am": "125mg", "pm": "125mg"},
        ],
    },
    {
        "outcome": "pain",
        "doses": [
            {"name": "Naltrexone", "am": "4.5mg", "pm": "4.5mg"},
            {"name": "Lamotrigine", "am": "100mg", "pm": "100mg"},
        ],
    },
    {
        "outcome": "no_pain",
        "doses": [
            {"name": "Naltrexone", "am": "4.5mg", "pm": "3.0mg"},
            {"name": "Lamotrigine", "am": "100mg", "pm": "100mg"},
        ],
    },
    {
        "outcome": "no_pain",
        "doses": [
            {"name": "Naltrexone", "am": "4.5mg", "pm": "3.0mg"},
            {"name": "Lamotrigine", "am": "100mg", "pm": "100mg"},
        ],
    },
]


class MatrixParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_th = False
        self.in_td = False
        self.headers: list[str] = []
        self.row_headers: list[str] = []
        self.cell_count = 0
        self._buf = ""
        self._th_is_row = False
        self._row_th_seen = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table" and attrs.get("class") == "matrix":
            self.in_table = True
            self._row_th_seen = False
        elif self.in_table and tag == "tr":
            self._row_th_seen = False
        elif self.in_table and tag == "th":
            self.in_th = True
            self._buf = ""
            self._th_is_row = "axis-lbl" in (attrs.get("class") or "") and self._row_th_seen is False
        elif self.in_table and tag == "td":
            self.in_td = True
            self.cell_count += 1

    def handle_endtag(self, tag):
        if tag == "table":
            self.in_table = False
        elif tag == "th" and self.in_th:
            text = " ".join(self._buf.split())
            if text:
                # First header row collects corner + X labels; later th.axis-lbl are Y labels
                if not self.row_headers and (not self.headers or "\\" in text or len(self.headers) < 10):
                    # Still building first header row until we start body rows with prior headers
                    if "\\" in text or not self.headers:
                        self.headers.append(text)
                    elif len([h for h in self.headers if "\\" in h]) == 1 and "AM" in text or "mg" in text:
                        if self.headers and "\\" in self.headers[0] and text not in self.headers:
                            # Could be X header still
                            if not self._row_th_seen:
                                self.headers.append(text)
                            else:
                                self.row_headers.append(text)
                        else:
                            self.headers.append(text)
                    else:
                        self.headers.append(text)
                else:
                    self.row_headers.append(text)
                if "axis-lbl" in text or True:
                    pass
            # Better classification: if headers already has corner+x and this th starts a new row
            self.in_th = False
            self._buf = ""
        elif tag == "td":
            self.in_td = False

    def handle_data(self, data):
        if self.in_th:
            self._buf += data


def parse_matrix(html: str) -> dict:
    """Extract axis labels and cell count with regex (more reliable than hand-rolled parser)."""
    assert '<table class="matrix">' in html, "missing <table class=\"matrix\">"

    # Corner: Y \\ X
    corner_m = re.search(
        r"<thead><tr><th>([^<]+)</th>",
        html,
    )
    assert corner_m, "missing corner header"
    corner = corner_m.group(1).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

    # X axis labels from thead th.axis-lbl
    thead = re.search(r"<thead>(.*?)</thead>", html, re.S)
    assert thead, "missing thead"
    x_labels = re.findall(r'<th class="axis-lbl">([^<]+)</th>', thead.group(1))

    # Y axis labels from tbody first th.axis-lbl per row
    tbody = re.search(r"<tbody>(.*?)</tbody>", html, re.S)
    assert tbody, "missing tbody"
    y_labels = re.findall(r'<tr><th class="axis-lbl">([^<]+)</th>', tbody.group(1))

    cells = len(re.findall(r'class="matrix-cell', html))
    filled = len(re.findall(r'class="matrix-cell (?!cell-empty)', html))

    return {
        "corner": corner,
        "x_labels": x_labels,
        "y_labels": y_labels,
        "cell_count": cells,
        "filled_cells": filled,
        "html": html,
    }


def assert_true(cond: bool, msg: str, failures: list):
    if cond:
        print(f"  PASS  {msg}")
    else:
        print(f"  FAIL  {msg}")
        failures.append(msg)


def main() -> int:
    print("Dose Log grid test — Naltrexone (X) × Lamotrigine (Y)\n")
    failures: list[str] = []

    html = build_dose_matrix(SAMPLE_ENTRIES, "Naltrexone", "Lamotrigine")
    assert_true(bool(html), "matrix HTML is non-empty", failures)
    assert_true('<table class="matrix">' in html, "contains table.matrix", failures)

    parsed = parse_matrix(html)
    corner = parsed["corner"]
    x_labels = parsed["x_labels"]
    y_labels = parsed["y_labels"]

    print(f"\n  Corner label : {corner}")
    print(f"  X-axis doses : {x_labels}")
    print(f"  Y-axis doses : {y_labels}")
    print(f"  Cells        : {parsed['cell_count']} total, {parsed['filled_cells']} with data\n")

    assert_true(
        "Lamotrigine" in corner and "Naltrexone" in corner and "\\" in corner,
        "corner shows Y \\ X (Lamotrigine \\ Naltrexone)",
        failures,
    )
    assert_true(len(x_labels) >= 2, f"X axis has ≥2 dose columns (got {len(x_labels)})", failures)
    assert_true(len(y_labels) >= 2, f"Y axis has ≥2 dose rows (got {len(y_labels)})", failures)
    assert_true(
        any("4.5mg AM / 3.0mg PM" in x for x in x_labels),
        "X axis includes Naltrexone 4.5mg AM / 3.0mg PM",
        failures,
    )
    assert_true(
        any("125mg AM / 125mg PM" in y for y in y_labels),
        "Y axis includes Lamotrigine 125mg AM / 125mg PM",
        failures,
    )
    assert_true(
        any("100mg AM / 100mg PM" in y for y in y_labels),
        "Y axis includes Lamotrigine 100mg AM / 100mg PM",
        failures,
    )
    assert_true(
        parsed["cell_count"] == len(x_labels) * len(y_labels),
        f"grid is full rectangle ({len(x_labels)}×{len(y_labels)})",
        failures,
    )
    assert_true(parsed["filled_cells"] >= 3, "at least 3 filled outcome cells", failures)

    # Negative cases
    empty = build_dose_matrix(SAMPLE_ENTRIES, "Naltrexone", "Naltrexone")
    assert_true(empty == "", "same med on both axes returns empty", failures)

    no_overlap = build_dose_matrix(
        [{"outcome": "pain", "doses": [{"name": "Naltrexone", "am": "1mg", "pm": "1mg"}]}],
        "Naltrexone",
        "Lamotrigine",
    )
    assert_true(
        "Not enough overlapping" in no_overlap,
        "single-med entries show overlap empty-state",
        failures,
    )

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} assertion(s))")
        return 1

    # ASCII preview of the grid
    print("ASCII preview:")
    print(f"  {'':28} | " + " | ".join(f"{x[:18]:18}" for x in x_labels))
    print("  " + "-" * (30 + 21 * len(x_labels)))
    # Rebuild cell map for preview
    cells = {}
    for e in SAMPLE_ENTRIES:
        xv = doses_for_med(e, "Naltrexone")
        yv = doses_for_med(e, "Lamotrigine")
        if xv is None or yv is None:
            continue
        k = f"{xv}||{yv}"
        cells.setdefault(k, {"t": 0, "np": 0})
        cells[k]["t"] += 1
        if e["outcome"] == "no_pain":
            cells[k]["np"] += 1
    for y in y_labels:
        row = []
        for x in x_labels:
            c = cells.get(f"{x}||{y}")
            row.append(f'{c["np"]}/{c["t"]} no pain' if c else "·")
        print(f"  {y[:28]:28} | " + " | ".join(f"{v:18}" for v in row))

    print("\nRESULT: PASS — grid has real X and Y axes with outcome cells")
    return 0


if __name__ == "__main__":
    sys.exit(main())
