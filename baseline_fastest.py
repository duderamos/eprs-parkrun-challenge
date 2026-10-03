#!/usr/bin/env python3
"""Build a CSV of parkrun baselines (fastest parkrun in a given year).

Usage:
    ./baseline_fastest.py ids.txt > baselines.csv
    cat ids.txt | ./baseline_fastest.py > baselines.csv
    ./baseline_fastest.py --before 2026-10-04 ids.txt   # only runs before Round 1
    ./baseline_fastest.py --year 2025 ids.txt

Input: one parkrunner per line. Accepts "7949802", "A7949802" or a full
profile URL. Blank lines and lines starting with # are ignored.
"""

import argparse
import csv
import re
import sys
import time
import urllib.request
from datetime import date, datetime
from html.parser import HTMLParser

ALL_RESULTS_URL = "https://www.parkrun.com.au/parkrunner/{id}/all/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class AllResultsParser(HTMLParser):
    """Extracts the runner's name and the rows of the 'All Results' table."""

    def __init__(self):
        super().__init__()
        self.name = ""
        self.rows = []
        self._in_h2 = False
        self._in_table = False
        self._in_caption = False
        self._caption = ""
        self._is_all_results = False
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "h2" and not self.name:
            self._in_h2 = True
        elif tag == "table":
            self._in_table = True
            self._caption = ""
            self._is_all_results = False
        elif self._in_table and tag == "caption":
            self._in_caption = True
        elif self._is_all_results and tag == "tr":
            self._row = []
        elif self._row is not None and tag == "td":
            self._cell = ""

    def handle_endtag(self, tag):
        if tag == "h2":
            self._in_h2 = False
        elif tag == "caption" and self._in_caption:
            self._in_caption = False
            self._is_all_results = " ".join(self._caption.split()) == "All Results"
        elif tag == "td" and self._cell is not None:
            self._row.append(self._cell.strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
        elif tag == "table":
            self._in_table = self._is_all_results = False

    def handle_data(self, data):
        if self._in_h2:
            self.name += data
        if self._in_caption:
            self._caption += data
        if self._cell is not None:
            self._cell += data


def parse_id(line):
    m = re.search(r"(\d+)", line)
    return m.group(1) if m else None


def to_seconds(t):
    secs = 0
    for p in t.split(":"):
        secs = secs * 60 + int(p)
    return secs


def fmt_time(secs):
    h, rem = divmod(round(secs), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fetch(runner_id):
    req = urllib.request.Request(
        ALL_RESULTS_URL.format(id=runner_id), headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fastest_for(runner_id, year, before):
    """Returns (name, fastest run as (date, event, time) or None, runs counted)."""
    p = AllResultsParser()
    p.feed(fetch(runner_id))
    name = re.sub(r"\s*\(A\d+\)$", "", " ".join(p.name.split()))

    runs = []
    for row in p.rows:
        # Columns: Event, Run Date, Run Number, Pos, Time, Age Grade, PB?
        if len(row) < 5:
            continue
        event, run_date, time_str = row[0], row[1], row[4]
        run_date = datetime.strptime(run_date, "%d/%m/%Y").date()
        if run_date.year != year or (before and run_date >= before):
            continue
        runs.append((run_date, event, time_str))

    fastest = min(runs, key=lambda r: to_seconds(r[2]), default=None)
    return name, fastest, len(runs)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", nargs="?", help="file with parkrun IDs (default: stdin)")
    ap.add_argument("--year", type=int, default=2026, help="year to take the fastest run from")
    ap.add_argument(
        "--before",
        type=date.fromisoformat,
        help="only count runs strictly before this date (YYYY-MM-DD), e.g. Round 1",
    )
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    args = ap.parse_args()

    src = open(args.file) if args.file else sys.stdin
    ids = []
    for line in src:
        line = line.strip()
        if line and not line.startswith("#"):
            rid = parse_id(line)
            if rid:
                ids.append(rid)
            else:
                print(f"skipping unrecognised line: {line!r}", file=sys.stderr)

    out = csv.writer(sys.stdout)
    out.writerow([
        "parkrun_id", "name", "fastest_date", "fastest_event", "fastest_time",
        "runs_in_year", "baseline_seconds", "baseline",
    ])

    for n, rid in enumerate(ids):
        if n:
            time.sleep(args.delay)
        try:
            name, fastest, count = fastest_for(rid, args.year, args.before)
        except Exception as e:
            print(f"{rid}: failed to fetch/parse ({e})", file=sys.stderr)
            out.writerow([rid, "ERROR"])
            continue

        if fastest:
            run_date, event, time_str = fastest
            secs = to_seconds(time_str)
            out.writerow([rid, name, run_date.isoformat(), event, time_str,
                          count, secs, fmt_time(secs)])
        else:
            out.writerow([rid, name, "", "", "", 0, "", ""])
            print(f"{rid} ({name}): no runs in {args.year}", file=sys.stderr)
        sys.stdout.flush()
        print(f"{rid} ({name}): {fmt_time(to_seconds(fastest[2])) if fastest else 'no runs'}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
