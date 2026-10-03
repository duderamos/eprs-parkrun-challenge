#!/usr/bin/env python3
"""Build a CSV of parkrun baselines (average of the last 3 parkruns).

Usage:
    ./baseline-avg.py ids.txt > baselines.csv
    cat ids.txt | ./baseline-avg.py > baselines.csv
    ./baseline-avg.py --before 2026-10-04 ids.txt   # only runs before Round 1

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

PROFILE_URL = "https://www.parkrun.com.au/parkrunner/{id}/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
RUNS_FOR_BASELINE = 3


class ProfileParser(HTMLParser):
    """Extracts the runner's name and the rows of the 'Most Recent parkruns' table."""

    def __init__(self):
        super().__init__()
        self.name = ""
        self.rows = []
        self._in_h2 = False
        self._seen_most_recent = False
        self._in_table = False
        self._in_tbody = False
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h2" and not self.name:
            self._in_h2 = True
        elif tag == "h3" and attrs.get("id") == "most-recent":
            self._seen_most_recent = True
        elif tag == "table" and self._seen_most_recent and not self.rows:
            self._in_table = True
        elif self._in_table and tag == "tbody":
            self._in_tbody = True
        elif self._in_tbody and tag == "tr":
            self._row = []
        elif self._row is not None and tag == "td":
            self._cell = ""

    def handle_endtag(self, tag):
        if tag == "h2":
            self._in_h2 = False
        elif tag == "td" and self._cell is not None:
            self._row.append(self._cell.strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None
        elif tag == "table" and self._in_table:
            self._in_table = self._in_tbody = False
            self._seen_most_recent = False

    def handle_data(self, data):
        if self._in_h2:
            self.name += data
        if self._cell is not None:
            self._cell += data


def parse_id(line):
    m = re.search(r"(\d+)", line)
    return m.group(1) if m else None


def to_seconds(t):
    parts = [int(p) for p in t.split(":")]
    secs = 0
    for p in parts:
        secs = secs * 60 + p
    return secs


def fmt_time(secs):
    secs = round(secs)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fetch(runner_id):
    req = urllib.request.Request(
        PROFILE_URL.format(id=runner_id), headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def baseline_for(runner_id, before):
    p = ProfileParser()
    p.feed(fetch(runner_id))
    name = re.sub(r"\s*\(A\d+\)$", "", " ".join(p.name.split()))

    runs = []
    for row in p.rows:
        # Columns: Event, Run Date, Gender Pos, Overall Pos, Time, Age Grade
        if len(row) < 6:
            continue
        event, run_date, time_str = row[0], row[1], row[4]
        run_date = datetime.strptime(run_date, "%d/%m/%Y").date()
        if before and run_date >= before:
            continue
        runs.append((run_date, event, time_str))

    runs.sort(key=lambda r: r[0], reverse=True)
    return name, runs[:RUNS_FOR_BASELINE]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", nargs="?", help="file with parkrun IDs (default: stdin)")
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

    header = ["parkrun_id", "name"]
    for i in range(1, RUNS_FOR_BASELINE + 1):
        header += [f"run{i}_date", f"run{i}_event", f"run{i}_time"]
    header += ["runs_counted", "baseline_seconds", "baseline"]

    out = csv.writer(sys.stdout)
    out.writerow(header)

    for n, rid in enumerate(ids):
        if n:
            time.sleep(args.delay)
        try:
            name, runs = baseline_for(rid, args.before)
        except Exception as e:
            print(f"{rid}: failed to fetch/parse ({e})", file=sys.stderr)
            out.writerow([rid, "ERROR"])
            continue

        row = [rid, name]
        for i in range(RUNS_FOR_BASELINE):
            row += [runs[i][0].isoformat(), runs[i][1], runs[i][2]] if i < len(runs) else ["", "", ""]

        if runs:
            avg = sum(to_seconds(r[2]) for r in runs) / len(runs)
            row += [len(runs), f"{avg:.1f}", fmt_time(avg)]
        else:
            row += [0, "", ""]
        if len(runs) < RUNS_FOR_BASELINE:
            print(f"{rid} ({name}): only {len(runs)} run(s) found", file=sys.stderr)

        out.writerow(row)
        sys.stdout.flush()
        print(f"{rid} ({name}): {row[-1] or 'no runs'}", file=sys.stderr)


if __name__ == "__main__":
    main()
